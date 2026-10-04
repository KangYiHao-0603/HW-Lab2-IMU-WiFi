/*
 * imu.h
 *
 * LSM6DSL driver (I2C2, address 0xD4) for the B-L475E-IOT01A:
 *  - 3D accelerometer (mg) and 3D gyroscope (mdps)
 *  - Significant motion detection routed to INT1 -> PD11 (EXTI11)
 */

#ifndef INC_IMU_H_
#define INC_IMU_H_

#include "main.h"

#define LSM6DSL_ADDR          0xD4   /* 8-bit I2C address (SA0 = 0)            */
#define LSM6DSL_WHO_AM_I_VAL  0x6A   /* expected WHO_AM_I value                 */

/* Significant motion threshold (SM_THS). Smaller = triggers sooner. */
#define SM_THRESHOLD          6

/* LSM6DSL INT1 is wired to PD11 on this board */
#define LSM6DSL_INT1_Pin        GPIO_PIN_11
#define LSM6DSL_INT1_GPIO_Port  GPIOD

/* LED2 (green) on PB14, toggled on every significant motion event */
#define LED2_Pin                GPIO_PIN_14
#define LED2_GPIO_Port          GPIOB

extern volatile uint8_t sm_flag;     /* set by the EXTI11 interrupt  */
extern uint8_t imu_who_am_i;         /* watch in debugger: must be 0x6A */

void    imu_gpio_init(void);         /* PD11 EXTI + PB14 LED          */
int     imu_init(void);              /* returns 1 if LSM6DSL answers  */
void    imu_read(int32_t acc_mg[3], int32_t gyr_mdps[3]);
void    sigmot_init(uint8_t threshold);
uint8_t sigmot_read_and_clear(void); /* returns FUNC_SRC1            */
void    sigmot_rearm(void);

#endif /* INC_IMU_H_ */
