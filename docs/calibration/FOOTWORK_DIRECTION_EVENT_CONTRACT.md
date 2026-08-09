# Footwork Direction and Event Contract V1

## 目的

定義步法測驗中的方向座標、Event 邊界與回中概念。

本文件先固定行為契約，再依人工評閱與多影片證據調整 Calibration。

## 1. 拍攝與方向座標

V1 使用固定單一正面攝影機。

- 球員面向攝影機。
- 左右方向以球員本人為準，不以觀看者為準。
- 方向描述的是球員到達的目標區域。
- 方向不描述球員使用的移動技術。

目前角度定義：

| 角度中心 | 方向 |
|---:|---|
| 0° | RIGHT |
| 45° | RIGHT_FRONT |
| 90° | FRONT |
| 135° | LEFT_FRONT |
| ±180° | LEFT |
| -135° | LEFT_BACK |
| -90° | BACK |
| -45° | RIGHT_BACK |

## 2. 方向與技術分離

以下動作即使移動方式不同，只要到達相同目標區域，方向應相同：

- 弓箭步
- 轉身跨步
- 反手跨步
- 交叉步
- 墊步

例如球員向右側移動：

- 使用單一步弓箭步，方向仍為 RIGHT。
- 使用轉身跨步，方向仍為 RIGHT。

移動技術未來可由獨立 Feature 評估，不應改變 Direction Label。

## 3. 中心概念

V1 區分兩種中心：

### Strict Center

球員回到原始中心附近。

用途：

- 判斷完整回中。
- 計算 Recovery Time。
- 產生 returned_to_center。

目前暫定門檻：

`offset <= 0.05`

### Base Zone

球員已回到可銜接下一方向的位置，例如 T 字附近，但未必回到原始中心點。

用途：

- 協助切分連續 Event。
- 不等同完整回中。
- 不直接視為 returned_to_center。

Base Zone 門檻必須經影片校正後決定，不在本文件先固定數值。

## 4. Event 定義

一個 Event 表示：

1. 球員由中心或 Base Zone 開始向外移動。
2. 到達一個主要方向的最大位移區域。
3. 開始回復或轉向下一個方向。

## 5. Event 完成方式

Event 可以透過以下任一方式完成：

### A. Strict Return

球員進入 Strict Center 並維持指定 Frames。

結果：

- Event 完成。
- returned_to_center = true。
- 可計算完整 Recovery Time。

### B. Base-Zone Transition

球員未進入 Strict Center，但符合：

1. 已由前一個 Peak 明顯回復。
2. 進入 Base Zone。
3. 接著再次向外移動。
4. 新移動方向與前一方向有明顯差異。

結果：

- 前一 Event 可被切分。
- returned_to_center = false。
- Recovery Time 不應假裝成完整回中時間。
- 新方向建立新的 Event。

## 6. 邊界方向

位於兩個 Sector 邊界的有效移動，不應只因角度接近邊界而直接成為 UNKNOWN。

例如：

`22.498°`

此移動位於 RIGHT 與 RIGHT_FRONT 邊界，但具有有效位移，因此應：

- 保留最佳方向候選。
- 標記 boundary_ambiguous = true。
- 降低方向信心。
- 不因邊界本身直接丟失 Event。

UNKNOWN 應保留給：

- 位移不足。
- Pose Evidence 不足。
- 無法取得可靠方向向量。
- 多項證據互相衝突。

## 7. Recovery Time

Recovery Time 只描述：

`到達最大位移 → 回到 Strict Center`

若僅回到 Base Zone：

- 可以保留 provisional recovery evidence。
- 不應標示為完整回中時間。
- 不應與 Strict Return 的 Recovery Time 混合比較。

## 8. 已知驗證案例

### FW_001

人工觀察：

- 八方向皆完成。
- 回位快速。
- 動作流暢穩定。

系統現象：

- Event 8/8。
- RIGHT_FRONT 與 LEFT_FRONT 重複。
- 缺少 LEFT_BACK 與 RIGHT。
- Body Stability 與人工觀察不一致。

### FW_002

人工觀察：

- 八方向皆完成。
- 第一段 RIGHT_FRONT → LEFT_FRONT 之間只回到 T 字附近。
- 攝影機抖動明顯。

系統現象：

- Event 6/8。
- 第一個 Event Recovery Time 為 4.149 秒，疑似合併兩次移動。
- 22.498° 的有效移動因信心 0.2501 被標為 UNKNOWN。
- Body Stability 與人工觀察不一致。

## 9. 實作順序

1. 為 Sector Boundary 建立單元測試。
2. 保留邊界方向候選，不直接改為 UNKNOWN。
3. 為 Base-Zone Transition 建立 Event 測試。
4. 實作連續方向切分。
5. 重新執行 FW_001、FW_002。
6. 最後才檢討 x_scale、y_scale 與 Body Stability 門檻。
