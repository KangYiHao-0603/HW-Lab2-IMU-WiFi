/*
 * imu.c
 *
 * LSM6DSL accelerometer + gyroscope + significant motion detection
 * Register addresses and procedure: LSM6DSL datasheet and AN5040.
 */

#include "imu.h"

extern I2C_HandleTypeDef hi2c2;

/* ---------------- LSM6DSL registers ---------------- */
#define R_FUNC_CFG_ACCESS  0x01  /* bit7 FUNC_CFG_EN: access embedded-function bank A */
#define R_SM_THS           0x13  /* (bank A) significant motion threshold             */
#define R_INT1_CTRL        0x0D  /* bit6 INT1_SIGN_MOT                                */
#define R_WHO_AM_I         0x0F
#define R_CTRL1_XL         0x10  /* accel ODR[7:4], FS[3:2]                           */
#define R_CTRL2_G          0x11  /* gyro  ODR[7:4], FS[3:2]                           */
#define R_CTRL3_C          0x12  /* bit6 BDU, bit2 IF_INC, bit0 SW_RESET              */
#define R_CTRL10_C         0x19  /* bit2 FUNC_EN, bit1 PEDO_RST_STEP, bit0 SIGN_MOTION_EN */
#define R_OUTX_L_G         0x22  /* gyro  X,Y,Z  (6 bytes)                            */
#define R_OUTX_L_XL        0x28  /* accel X,Y,Z  (6 bytes)                            */
#define R_FUNC_SRC1        0x53  /* bit6 SIGN_MOTION_IA (cleared by reading)          */

volatile uint8_t sm_flag = 0;
uint8_t imu_who_am_i = 0;

/* ---------------- low-level I2C helpers ---------------- */
static void reg_write(uint8_t reg, uint8_t val)
{
    HAL_I2C_Mem_Write(&hi2c2, LSM6DSL_ADDR, reg, I2C_MEMADD_SIZE_8BIT, &val, 1, 10);
}

static uint8_t reg_read(uint8_t reg)
{
    uint8_t val = 0;
    HAL_I2C_Mem_Read(&hi2c2, LSM6DSL_ADDR, reg, I2C_MEMADD_SIZE_8BIT, &val, 1, 10);
    return val;
}

static void regs_read(uint8_t reg, uint8_t *buf, uint16_t len)
{
    HAL_I2C_Mem_Read(&hi2c2, LSM6DSL_ADDR, reg, I2C_MEMADD_SIZE_8BIT, buf, len, 10);
}

/* ---------------- GPIO: PD11 (LSM6DSL INT1) as EXTI, PB14 LED2 ---------------- */
void imu_gpio_init(void)
{
    GPIO_InitTypeDef g = {0};

    __HAL_RCC_GPIOD_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    /* PD11: rising-edge external interrupt (EXTI line 11) */
    g.Pin  = LSM6DSL_INT1_Pin;
    g.Mode = GPIO_MODE_IT_RISING;
    g.Pull = GPIO_PULLDOWN;
    HAL_GPIO_Init(LSM6DSL_INT1_GPIO_Port, &g);

    /* PB14: LED2 output */
    HAL_GPIO_WritePin(LED2_GPIO_Port, LED2_Pin, GPIO_PIN_RESET);
    g.Pin   = LED2_Pin;
    g.Mode  = GPIO_MODE_OUTPUT_PP;
    g.Pull  = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED2_GPIO_Port, &g);

    /* EXTI lines 10..15 share one interrupt vector.
     * Lower priority (larger number) than the Wi-Fi EXTI1 (priority 0). */
    HAL_NVIC_SetPriority(EXTI15_10_IRQn, 2, 0);
    HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);
}

/* ---------------- accelerometer + gyroscope ---------------- */
int imu_init(void)
{
    imu_who_am_i = reg_read(R_WHO_AM_I);
    if (imu_who_am_i != LSM6DSL_WHO_AM_I_VAL) {
        return 0;
    }

    reg_write(R_CTRL3_C, 0x01);          /* software reset */
    HAL_Delay(20);
    reg_write(R_CTRL3_C, 0x44);          /* BDU = 1, IF_INC = 1 (auto-increment) */
    reg_write(R_CTRL1_XL, 0x40);         /* accel 104 Hz, +-2 g   -> 0.061 mg/LSB  */
    reg_write(R_CTRL2_G,  0x44);         /* gyro  104 Hz, 500 dps -> 17.5 mdps/LSB */
    HAL_Delay(20);
    return 1;
}

void imu_read(int32_t acc_mg[3], int32_t gyr_mdps[3])
{
    uint8_t b[6];
    int i;

    regs_read(R_OUTX_L_XL, b, 6);
    for (i = 0; i < 3; i++) {
        int16_t raw = (int16_t)(b[2 * i] | (b[2 * i + 1] << 8));
        acc_mg[i] = (int32_t)raw * 61 / 1000;      /* 0.061 mg/LSB */
    }

    regs_read(R_OUTX_L_G, b, 6);
    for (i = 0; i < 3; i++) {
        int16_t raw = (int16_t)(b[2 * i] | (b[2 * i + 1] << 8));
        gyr_mdps[i] = (int32_t)raw * 35 / 2;       /* 17.5 mdps/LSB */
    }
}

/* ---------------- significant motion (AN5040) ---------------- */
void sigmot_init(uint8_t threshold)
{
    /* 1. open embedded-function bank A, set threshold, close bank A */
    reg_write(R_FUNC_CFG_ACCESS, 0x80);
    reg_write(R_SM_THS, threshold);
    reg_write(R_FUNC_CFG_ACCESS, 0x00);

    /* 2. accelerometer ODR must be >= 26 Hz (imu_init set 104 Hz) */

    /* 3. FUNC_EN + SIGN_MOTION_EN */
    reg_write(R_CTRL10_C, reg_read(R_CTRL10_C) | 0x05);

    /* 4. route significant motion interrupt to INT1 */
    reg_write(R_INT1_CTRL, reg_read(R_INT1_CTRL) | 0x40);

    /* clear anything pending */
    (void)reg_read(R_FUNC_SRC1);
}

uint8_t sigmot_read_and_clear(void)
{
    return reg_read(R_FUNC_SRC1);
}

/* reset the internal step counter so the detector can fire again */
void sigmot_rearm(void)
{
    uint8_t c10 = reg_read(R_CTRL10_C);
    reg_write(R_CTRL10_C, c10 | 0x02);              /* PEDO_RST_STEP = 1 */
    reg_write(R_CTRL10_C, c10 & (uint8_t)~0x02);    /* back to 0         */
}

/* ---------------- EXTI callback ----------------
 * Called by HAL_GPIO_EXTI_IRQHandler() for every EXTI line.
 * Keep it short: only set a flag, the main loop does the I2C work. */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == LSM6DSL_INT1_Pin) {
        sm_flag = 1;
    }
}
