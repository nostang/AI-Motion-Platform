# Measurement Specification

Version: v1.0  
Module: AI Motion  
Scope: Footwork Assessment  
Architecture Level: L3  
Status: Draft Approved

---

## 1. Purpose

Measurement Layer 的目的，是將 MediaPipe Pose Landmarker 輸出的身體 Landmark，轉換為可供後續動作事件辨識使用的客觀數值。

Measurement Layer 只負責量測，不負責：

- 判斷動作正確或錯誤
- 判定動作階段
- 計算技術分數
- 產生教練建議
- 判定羽球程度或正式等級

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

## 2. Input Data

每一個影片影格由 MediaPipe Pose Landmarker 提供：

- 33 個人體 Landmark
- Frame Index
- Timestamp
- Video FPS
- Landmark Visibility

每個 Landmark 至少包含：

```json
{
  "x": 0.52,
  "y": 0.68,
  "z": -0.11,
  "visibility": 0.98
}
```

欄位說明：

| 欄位 | 說明 |
| --- | --- |
| `x` | Landmark 在畫面水平方向的正規化座標 |
| `y` | Landmark 在畫面垂直方向的正規化座標 |
| `z` | MediaPipe 推估的前後深度 |
| `visibility` | Landmark 在目前影格中可被辨識的可信程度 |

第一版主要使用 `x`、`y` 與 `visibility`。

---

## 3. Measurement Principles

### 3.1 數值優先

能以數值表示的項目，優先輸出客觀數值，不直接輸出：

- 好
- 不好
- 穩定
- 不穩定
- 正確
- 錯誤

以上判斷應交由後續的 Footwork Event 或 Rule Engine 處理。

### 3.2 使用正規化座標

第一版使用 MediaPipe 提供的正規化座標。

Measurement Layer 不直接宣稱：

- 公尺
- 公分
- 公尺／秒

若未來完成球場座標校正，才可將部分量測值轉換為實際距離或速度。

### 3.3 不在此層加入羽球判斷

Measurement Layer 不判斷：

- 是否回中心
- 是否完成米字步
- 是否有啟動步
- 是否有多餘碎步
- 動作是否正確
- 技術表現是否良好

以上項目由 Footwork Event 或 Rule Engine 處理。

### 3.4 低可信 Landmark 不直接採用

若必要 Landmark 的 `visibility` 低於系統設定門檻，該次 Measurement 應標記為：

- 無效
- 低可信
- 不可直接用於後續判斷

不得將低可信資料直接視為可靠量測結果。

### 3.5 Measurement 不直接評分

Measurement Layer 的輸出只能是：

- 座標
- 角度
- 距離
- 位移
- 速度
- 時間
- 有效性資訊

不得直接輸出：

- 分數
- 星等
- 等級
- 教練建議

---

## 4. Measurement List

### M001｜Pelvis Center Position

#### 中文名稱

骨盆中心位置

#### Description

取左髖與右髖 Landmark 的中點，作為骨盆中心位置。

此位置是人體軀幹移動的代理點，不宣稱為完整人體重心。

#### Input

- Landmark 23：Left Hip
- Landmark 24：Right Hip

#### Calculation

```text
center_x = (left_hip.x + right_hip.x) / 2
center_y = (left_hip.y + right_hip.y) / 2
```

#### Output

```json
{
  "measurement_id": "M001",
  "x": 0.51,
  "y": 0.63,
  "valid": true
}
```

#### Used By

- Center Region
- Pelvis Displacement
- Pelvis Velocity
- Footwork Event
- Recovery Detection

#### Status

✅ Implemented

---

### M002｜Knee Angle

#### 中文名稱

膝關節角度

#### Description

由髖部、膝蓋與腳踝三點計算膝關節夾角。

左右膝分別計算。

#### Input

左膝：

- Landmark 23：Left Hip
- Landmark 25：Left Knee
- Landmark 27：Left Ankle

右膝：

- Landmark 24：Right Hip
- Landmark 26：Right Knee
- Landmark 28：Right Ankle

#### Calculation

以膝蓋為角度中心，計算：

- 髖部至膝蓋向量
- 腳踝至膝蓋向量

兩者之間的夾角。

#### Output

```json
{
  "measurement_id": "M002",
  "left_knee_angle": 151.4,
  "right_knee_angle": 168.2,
  "valid": true
}
```

#### Used By

- Ready Position Analysis
- Lower Body Posture
- Split Step Candidate Detection
- Reach Position Analysis

#### Status

✅ Implemented

---

### M003｜Foot Position

#### 中文名稱

左右腳位置

#### Description

紀錄左右腳踝、腳跟與腳尖的正規化座標。

第一版主要以腳踝位置作為移動分析基準。

腳跟與腳尖保留供後續分析：

- 腳步方向
- 落地狀態
- 腳尖朝向
- 腳步順序

#### Input

- Landmark 27：Left Ankle
- Landmark 28：Right Ankle
- Landmark 29：Left Heel
- Landmark 30：Right Heel
- Landmark 31：Left Foot Index
- Landmark 32：Right Foot Index

#### Output

```json
{
  "measurement_id": "M003",
  "left_ankle": {
    "x": 0.43,
    "y": 0.88
  },
  "right_ankle": {
    "x": 0.57,
    "y": 0.87
  },
  "left_heel": {
    "x": 0.42,
    "y": 0.90
  },
  "right_heel": {
    "x": 0.58,
    "y": 0.89
  },
  "left_foot_index": {
    "x": 0.45,
    "y": 0.91
  },
  "right_foot_index": {
    "x": 0.60,
    "y": 0.90
  },
  "valid": true
}
```

#### Used By

- Foot Distance
- Foot Movement Detection
- Step Count
- Foot Sequence
- Extra Step Detection
- Split Step Candidate Detection

#### Status

⏳ Planned

---

### M004｜Foot Distance

#### 中文名稱

雙腳間距

#### Description

計算左右腳之間的正規化距離。

第一版預設使用左右腳踝座標。

若後續測試發現腳跟或腳尖更穩定，可調整計算來源。

#### Input

- Left Ankle Position
- Right Ankle Position

#### Calculation

```text
distance = sqrt(
  (right_x - left_x)^2
  +
  (right_y - left_y)^2
)
```

#### Output

```json
{
  "measurement_id": "M004",
  "foot_distance_normalized": 0.18,
  "valid": true
}
```

#### Used By

- Ready Position Analysis
- Split Step Candidate Detection
- Footwork Sequence Analysis

#### Status

⏳ Planned

---

### M005｜Pelvis Displacement

#### 中文名稱

骨盆中心位移

#### Description

比較目前影格與前一影格的骨盆中心位置差異。

輸出：

- 水平位移
- 垂直位移
- 總位移量

#### Input

- Current Pelvis Center
- Previous Pelvis Center

#### Calculation

```text
delta_x = current_x - previous_x
delta_y = current_y - previous_y

distance = sqrt(
  delta_x^2
  +
  delta_y^2
)
```

#### Output

```json
{
  "measurement_id": "M005",
  "delta_x": 0.012,
  "delta_y": -0.006,
  "distance": 0.0134,
  "valid": true
}
```

#### Used By

- Movement Start Detection
- Movement Direction
- Center Leave Detection
- Recovery Direction Detection
- Reach Candidate Detection

#### Status

🟡 Partially Implemented

目前已保存骨盆中心軌跡，但尚未整理成正式位移輸出。

---

### M006｜Pelvis Velocity

#### 中文名稱

骨盆中心移動速度

#### Description

以骨盆中心位移除以影格時間差，計算骨盆中心的正規化移動速度。

第一版不得標示為公尺／秒。

#### Input

- Pelvis Displacement
- Current Timestamp
- Previous Timestamp

#### Calculation

```text
velocity_x = delta_x / delta_time
velocity_y = delta_y / delta_time
speed = distance / delta_time
```

#### Output

```json
{
  "measurement_id": "M006",
  "velocity_x": 0.31,
  "velocity_y": -0.12,
  "speed": 0.33,
  "unit": "normalized_per_second",
  "valid": true
}
```

#### Used By

- READY State
- MOVE State
- REACH State
- RECOVER State
- Standing Stability
- Movement Timing

#### Status

⏳ Planned

---

### M007｜Shoulder Line Angle

#### 中文名稱

肩線傾斜角度

#### Description

計算左右肩膀連線相對於畫面水平線的傾斜角度。

此數值只描述肩線方向，不直接代表穩定或不穩定。

#### Input

- Landmark 11：Left Shoulder
- Landmark 12：Right Shoulder

#### Calculation

```text
angle = atan2(
  right_shoulder.y - left_shoulder.y,
  right_shoulder.x - left_shoulder.x
)
```

輸出需轉換為角度。

#### Output

```json
{
  "measurement_id": "M007",
  "shoulder_line_angle": 4.8,
  "valid": true
}
```

#### Used By

- Torso Tilt Analysis
- Upper Body Stability
- Reach Position Analysis
- Recovery Stability

#### Status

⏳ Planned

---

### M008｜Pelvis Line Angle

#### 中文名稱

骨盆線傾斜角度

#### Description

計算左右髖部連線相對於畫面水平線的傾斜角度。

此數值可用於觀察骨盆在移動與回中心過程中的左右傾斜變化。

#### Input

- Landmark 23：Left Hip
- Landmark 24：Right Hip

#### Calculation

```text
angle = atan2(
  right_hip.y - left_hip.y,
  right_hip.x - left_hip.x
)
```

輸出需轉換為角度。

#### Output

```json
{
  "measurement_id": "M008",
  "pelvis_line_angle": 3.2,
  "valid": true
}
```

#### Used By

- Pelvis Stability
- Reach Position Analysis
- Recovery Stability

#### Status

⏳ Planned

---

## 5. Items Outside the Measurement Layer

以下內容不得直接由 Measurement Layer 判斷：

| 項目 | 所屬層級 |
| --- | --- |
| 是否離開中心 | Footwork Event |
| 是否返回中心 | Footwork Event |
| 是否完成一個方向 | Footwork Event |
| 回中心耗時 | Footwork Event |
| 是否有多餘碎步 | Footwork Event / Rule Engine |
| 是否有啟動步 | Footwork Event |
| 骨盆是否穩定 | Rule Engine |
| 腳步是否正確 | Rule Engine |
| 動作分數 | Rule Engine |
| 教練建議 | Report |

---

## 6. MVP Priority

| Priority | Measurement |
| --- | --- |
| P0 | M001 Pelvis Center Position |
| P0 | M003 Foot Position |
| P0 | M004 Foot Distance |
| P0 | M005 Pelvis Displacement |
| P0 | M006 Pelvis Velocity |
| P1 | M002 Knee Angle |
| P1 | M007 Shoulder Line Angle |
| P1 | M008 Pelvis Line Angle |

---

## 7. Current Implementation Status

| ID | Measurement | Status |
| --- | --- | --- |
| M001 | Pelvis Center Position | ✅ Implemented |
| M002 | Knee Angle | ✅ Implemented |
| M003 | Foot Position | ⏳ Planned |
| M004 | Foot Distance | ⏳ Planned |
| M005 | Pelvis Displacement | 🟡 Partial |
| M006 | Pelvis Velocity | ⏳ Planned |
| M007 | Shoulder Line Angle | ⏳ Planned |
| M008 | Pelvis Line Angle | ⏳ Planned |

---

## 8. Acceptance Criteria

Measurement Layer V1 完成時，需符合：

- 每一幀可取得有效的骨盆中心位置
- 可輸出左右膝關節角度
- 可取得左右腳位置
- 可計算雙腳間距
- 可計算骨盆中心位移
- 可計算骨盆中心速度
- 可輸出肩線與骨盆線角度
- Landmark 可信度不足時可標示無效
- Measurement 不直接輸出評分
- 所有輸出可轉換成固定 JSON 格式