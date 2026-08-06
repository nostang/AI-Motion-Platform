# Footwork Event Specification

Version: v1.0  
Module: AI Motion  
Scope: Footwork Assessment  
Architecture Level: L3  
Status: Draft Approved

---

# 1. Purpose

Footwork Event Layer 的目的，是根據 Measurement Layer 所提供的數值，辨識球員目前所處的步法階段。

Footwork Event Layer 負責：

- 判斷步法流程
- 判斷是否完成一次完整米字步
- 計算事件時間
- 提供 Rule Engine 所需資訊

Footwork Event Layer 不負責：

- 技術評分
- 教練建議
- 羽球程度分級

整體資料流程：

```text
Video
↓
MediaPipe Pose
↓
Measurement
↓
Footwork Event
↓
Rule Engine
↓
Report
```

---

# 2. Event Definition

## Event Name

Footwork Event

---

## Event Description

一次 Footwork Event 定義為：

球員由中心位置開始，

移動至指定方向，

完成步法，

再返回中心，

等待下一次移動。

流程如下：

```text
READY
↓
MOVE
↓
REACH
↓
RECOVER
↓
READY
```

當再次回到 READY 時，

代表一個 Event 結束。

---

# 3. State Machine

## State 1｜READY

### Description

球員位於中心位置，

完成上一球，

等待下一次移動。

---

### Entry Condition

- Pelvis Center 位於 Center Region
- Pelvis Velocity 接近 0

---

### Exit Condition

- Pelvis Center 離開 Center Region

---

### Measurement Required

- M001 Pelvis Center Position
- M006 Pelvis Velocity

---

## State 2｜MOVE

### Description

球員開始往指定方向移動。

---

### Entry Condition

- Pelvis 離開 Center Region

---

### Exit Condition

符合以下任一：

- Pelvis Velocity 開始下降
- Pelvis Distance 達最大值

---

### Measurement Required

- M001
- M005
- M006

---

## State 3｜REACH

### Description

球員已抵達指定方向。

完成此次步法。

---

### Entry Condition

- Pelvis Distance 達最大值

---

### Exit Condition

- Pelvis 開始往中心方向移動

---

### Measurement Required

- M001
- M005
- M006

---

## State 4｜RECOVER

### Description

球員開始返回中心位置。

---

### Entry Condition

- Pelvis Distance 開始縮短

---

### Exit Condition

- Pelvis 重新進入 Center Region

---

### Measurement Required

- M001
- M005
- M006

---

# 4. Center Region

## Purpose

Center Region 定義球員的中心站位。

當 Pelvis Center 回到此區域，

即可判定：

READY。

---

## First Version

第一版不使用實際公分。

使用：

Normalized Coordinate。

```text
Center Region

Radius = R
```

R 為可調整參數。

待教練實測後決定。

---

# 5. Event Output

完成一次 Footwork Event 後，

需輸出：

```json
{
    "event_id":1,

    "direction":"RIGHT_FRONT",

    "completed":true,

    "return_center":true,

    "move_time":0.52,

    "recover_time":0.61,

    "total_time":1.13
}
```

---

# 6. Event Responsibilities

Footwork Event Layer 負責：

✅ 判定目前 State

✅ 判定是否完成 Event

✅ 判定是否回中心

✅ 計算移動時間

✅ 計算回中心時間

✅ 輸出 Event 資料

---

不得負責：

❌ 評分

❌ 技術分析

❌ 教練建議

❌ 雷達圖

---

# 7. Future Extension

目前僅支援：

- Footwork Event

未來可新增：

- Serve Event
- Clear Event
- Smash Event
- Drive Event
- Net Event

新增 Event 時，

Measurement Layer 不需修改。

僅新增：

- Event
- Rule

即可完成擴充。

---

# 8. Acceptance Criteria

Footwork Event V1 完成時，

需符合：

- 可辨識 READY
- 可辨識 MOVE
- 可辨識 REACH
- 可辨識 RECOVER
- 可完成一次完整 Event
- 可判斷是否成功回中心
- 可輸出 Move Time
- 可輸出 Recovery Time
- 可輸出 Event JSON