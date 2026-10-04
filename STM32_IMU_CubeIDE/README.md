# STM32 IoT Node(B-L475E-IOT01A)× STM32CubeIDE
LSM6DSL 加速度計／陀螺儀 → Wi-Fi(HTTP POST)→ Python 即時圖表
加分題:Significant motion 偵測(INT1 → PD11 EXTI 中斷)

本專案是以題目附的 iot2tangle `http-sender` 範例修改而成。

## 資料夾內容

```
firmware/                     ← STM32CubeIDE 專案(專案名稱 STM32WiFi)
  Core/Inc/config.h           ← ★ 要改:Wi-Fi 名稱、密碼、電腦 IP
  Core/Inc/imu.h              ← 新增:LSM6DSL 腳位、門檻值
  Core/Src/imu.c              ← 新增:加速度計、陀螺儀、significant motion、EXTI callback
  Core/Src/main.c             ← 修改:主迴圈(只在 USER CODE 區塊內)
  Core/Src/wifi.c / wifi.h    ← 修改:新增 wifi_post_json()
  Core/Src/stm32l4xx_it.c     ← 修改:新增 EXTI15_10_IRQHandler
host/
  host_gui.py                 ← 電腦端:HTTP 伺服器 + 即時圖表
  fake_node.py                ← 沒有板子時模擬板子送資料
```

## 一、安裝 STM32CubeIDE
1. 到 st.com 搜尋 **STM32CubeIDE**,登入 ST 帳號(免費註冊)後下載對應作業系統的版本並安裝。
2. 安裝過程中若詢問是否安裝 ST-LINK 驅動程式,請選安裝。
3. CubeMX 已內建在 CubeIDE 中,不需另外安裝。

## 二、匯入專案
1. 把 `firmware` 資料夾放到路徑中**沒有中文和空白**的位置,例如 `C:\stm32\firmware`。
2. 開啟 CubeIDE,選一個 workspace(同樣避免中文路徑)。
3. **File → Import…**,在搜尋框輸入 `ac6`,選 **Import ac6 System Workbench for STM32 Project**,Next。
   (此範例原本是 System Workbench 專案,CubeIDE 會自動轉換。)
4. 選擇 `firmware` 資料夾,Finish。如果跳出轉換確認視窗,按 **OK / Yes**。
   - 如果找不到上述選項:改用 **File → Import → General → Existing Projects into Workspace**,一樣選 `firmware` 資料夾,CubeIDE 會詢問是否轉換,選 Yes。

## 三、修改設定(`Core/Inc/config.h`)
```c
#define SSID   "你的WiFi名稱"
#define PSW    "你的WiFi密碼"
#define IPgw   "192.168.1.100"   // 執行 host_gui.py 那台電腦的 IP
#define PORTgw "8080"
```
- Wi-Fi 必須是 **2.4 GHz、WPA2**(ISM43362 不支援 5 GHz;範例用 `C3=4` 指定 WPA2)。
- 查電腦 IP:Windows `ipconfig`、Mac `ipconfig getifaddr en0`、Linux/RPi `hostname -I`。
- 建議用手機熱點:電腦和板子都連同一個熱點最簡單。

## 四、編譯與燒錄
1. 用 USB 線接板子的 **ST-LINK** 接頭(USB STLINK,靠近板子邊緣那個)。
2. 左側 Project Explorer 點選專案 → 按工具列的 **鐵鎚(Build)**,下方 Console 出現 `Build Finished. 0 errors` 即可。
3. 按 **綠色播放鍵(Run)** → 第一次會跳出設定視窗,選 **STM32 C/C++ Application** → OK(預設 ST-LINK GDB server 即可)。
4. 燒錄完成後按板子上的**黑色 RESET 鍵**。

## 五、電腦端
```bash
pip install matplotlib
python host_gui.py              # 預設 port 8080,可加 --csv log.csv 存檔
```
- Windows 第一次執行時防火牆會詢問,請勾選「私人網路」並允許。
- 沒有板子先測試:另開終端機執行 `python fake_node.py 127.0.0.1 8080`。

## 六、程式架構

### 通訊方式:HTTP POST
每一筆資料都是一個 HTTP 請求,沿用範例的 ISM43362 AT 指令:
```
P6=1                       開啟 TCP 連線
S3=<長度>\r<HTTP 請求>      送出資料
P6=0                       關閉連線
```
HTTP 請求內容:
```
POST /sensor_data HTTP/1.1
Content-Type: application/json
Content-Length: 75

{"type":"data","t":1234,"ax":12,"ay":-3,"az":1002,"gx":350,"gy":-70,"gz":0}
```
事件:
```
{"type":"event","t":5678,"name":"significant_motion","src":64,"count":1}
```
單位:加速度 mg、角速度 mdps(電腦端換成 dps)、t 為開機後毫秒數。

### 感測器設定(imu.c)
| 暫存器 | 值 | 意義 |
|---|---|---|
| WHO_AM_I (0Fh) | 讀到 6Ah | 確認 LSM6DSL 有回應 |
| CTRL3_C (12h) | 01h → 44h | 軟體重置;BDU=1、IF_INC=1(連續讀取多個暫存器) |
| CTRL1_XL (10h) | 40h | 加速度 104 Hz、±2 g → 0.061 mg/LSB |
| CTRL2_G (11h) | 44h | 陀螺儀 104 Hz、±500 dps → 17.5 mdps/LSB |
| OUTX_L_XL (28h) | 讀 6 bytes | 加速度 X/Y/Z |
| OUTX_L_G (22h) | 讀 6 bytes | 角速度 X/Y/Z |

原範例的陀螺儀程式被註解掉、加速度計只設 12.5 Hz,所以改成自己的 `imu.c`。

### 加分題:Significant motion(依 AN5040)
| 步驟 | 暫存器 | 值 |
|---|---|---|
| 開啟嵌入式功能暫存器組 | FUNC_CFG_ACCESS (01h) | 80h |
| 設定門檻 | SM_THS (13h, bank A) | 06h(`imu.h` 的 `SM_THRESHOLD`) |
| 關閉暫存器組 | FUNC_CFG_ACCESS (01h) | 00h |
| 加速度 ODR ≥ 26 Hz | CTRL1_XL (10h) | 已設 104 Hz |
| FUNC_EN + SIGN_MOTION_EN | CTRL10_C (19h) | \|= 05h |
| 輸出到 INT1 腳 | INT1_CTRL (0Dh) | \|= 40h |

中斷流程:
```
LSM6DSL INT1 ─▶ PD11 上升緣 ─▶ EXTI15_10_IRQHandler()(stm32l4xx_it.c)
            ─▶ HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_11) 清除中斷旗標
            ─▶ HAL_GPIO_EXTI_Callback()(imu.c):只設 sm_flag = 1
主迴圈看到 sm_flag ─▶ 讀 FUNC_SRC1(清除)─▶ LED2 反轉 ─▶ 送 event ─▶ PEDO_RST_STEP 重新啟動
```
- 中斷裡只設旗標,I2C 和 Wi-Fi 都在主迴圈做(中斷要越短越好,且 HAL 的阻塞函式不適合在中斷中呼叫)。
- PD11 的 EXTI 在 `imu_gpio_init()` 中用程式碼設定,**不要**再到 `.ioc` 把 PD11 設成 EXTI,否則 CubeMX 會再產生一個 `EXTI15_10_IRQHandler`,造成重複定義。
- 我修改的地方都在 `/* USER CODE BEGIN … */` 區塊內或新檔案中,用 CubeMX 重新產生程式碼也不會被覆蓋。

## 七、Demo 與除錯
| 狀況 | 現象 |
|---|---|
| 正常 | 電腦端顯示 `board: 192.168.x.x`,圖表有曲線,平放時 az ≈ 1000 mg |
| 偵測到 significant motion | 板子 LED2(綠色)切換;電腦畫面出現紅色 **SIGNIFICANT MOTION #n** 並畫紅線 |
| LED2 快速閃爍不停 | 讀不到 LSM6DSL(WHO_AM_I ≠ 0x6A) |
| 圖表一直沒資料 | Wi-Fi 帳密/頻段錯誤、IP 填錯、防火牆擋 8080、不同網段 |

- significant motion 底層是計步演算法,要**拿著板子走路**或**規律搖晃(約每秒 2 次,持續數秒)**才會觸發,單次敲擊通常不會。想更容易觸發,把 `imu.h` 的 `SM_THRESHOLD` 改小(例如 3)。
- 這個專案沒有 UART 輸出。可用 **Debug(蟲子圖示)** 執行,再開 **Window → Show View → Live Expressions**,加入 `imu_who_am_i`(應為 0x6A)、`sm_flag` 觀察。
- 每筆資料都要開、關一次 TCP 連線,實際更新率約數 Hz,屬正常現象;右上角會顯示實際接收頻率。
