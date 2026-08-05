# Rule Engine Specification

Version: v1.0  
Module: AI Motion  
Scope: Footwork Assessment  
Architecture Level: L3  
Status: Draft Approved

---

# 1. Purpose

Rule Engine Layer 的目的，是根據 Footwork Event 所輸出的事件資訊，依照羽球教練的技術規則，評估動作品質並產生評分結果。

Rule Engine 為整個 AI Motion 的核心知識層（Knowledge Layer）。

Rule Engine 負責：

- 技術分析
- 技術評分
- 缺失判定
- 建議代碼輸出

Rule Engine 不負責：

- 人體姿態辨識
- Measurement 計算
- Event 判定
- UI 呈現
- 雷達圖繪製

資料流程：

```text
Measurement
↓
Footwork Event
↓
Rule Engine
↓
Report
```

---

# 2. Rule Evaluation Flow

Rule Engine 採固定流程。

```text
Footwork Event
        │
        ▼
Observation
        │
        ▼
Evaluation
        │
        ▼
Score
        │
        ▼
Feedback Code
```

每新增一種羽球技術（發球、高遠球、殺球），

Rule Engine 流程皆保持一致。

僅調整 Observation 與 Evaluation 規則。

---

# 3. Observation Items

Observation 為 Rule Engine 的第一階段。

Observation 只回答：

> 發生了什麼？

Observation 不直接評分。

---

## O001｜Return to Center

### Description

球員是否成功返回中心位置。

### Input

- Footwork Event

### Output

```json
{
    "return_center": true
}
```

---

## O002｜Recovery Time

### Description

完成回中心所需時間。

### Input

- Footwork Event

### Output

```json
{
    "recovery_time":0.82
}
```

單位：

```text
second
```

---

## O003｜Footwork Correctness

### Description

觀察腳步是否符合預期。

第一版包含：

- 是否完成指定方向
- 是否出現多餘碎步
- 左右腳順序是否合理

### Output

```json
{
    "footwork_correct":true,
    "extra_steps":0
}
```

---

## O004｜Body Stability

### Description

完成步法後，

身體是否保持穩定。

第一版主要觀察：

- 骨盆穩定
- 軀幹穩定

未來可加入：

- 頭部晃動
- 上半身晃動

### Output

```json
{
    "body_stable":true
}
```

---

# 4. Evaluation

Evaluation 根據 Observation

轉換為技術表現。

第一版採 Rule Based。

---

## E001｜Center Recovery

Observation：

Return to Center

Evaluation：

```text
YES

↓

PASS
```

```text
NO

↓

FAIL
```

---

## E002｜Recovery Speed

Observation：

Recovery Time

Evaluation：

Recovery Time 越短，

代表回中心效率越高。

實際分級門檻，

待教練測試後建立。

---

## E003｜Footwork Technique

Observation：

Footwork Correctness

Evaluation：

依照：

- 腳步完成度
- 多餘碎步
- 腳步順序

進行技術評估。

---

## E004｜Movement Stability

Observation：

Body Stability

Evaluation：

依照：

- 骨盆穩定
- 軀幹穩定

判斷動作是否穩定。

---

# 5. Score

第一版採百分制。

四項 Observation

各占：

25 分。

| Observation | Weight |
|--------------|-------|
| Return Center | 25 |
| Recovery Speed | 25 |
| Footwork Technique | 25 |
| Body Stability | 25 |

總分：

```text
100
```

第二版可依教練建議調整權重。

---

# 6. Feedback Code

Rule Engine 不直接產生完整教練文字。

僅輸出 Feedback Code。

例如：

| Code | Description |
|------|-------------|
| F001 | Not Return Center |
| F002 | Recovery Too Slow |
| F003 | Extra Steps |
| F004 | Incorrect Footwork |
| F005 | Body Unstable |

Report Layer

依照 Feedback Code

轉換為：

- 中文建議
- 雷達圖
- 訓練建議

---

# 7. Rule Boundary

Rule Engine 不得：

- 修改 Measurement
- 修改 Event
- 修改 Landmark
- 修改影片資料

Rule Engine 僅能：

- 讀取 Event
- 分析 Rule
- 輸出結果

---

# 8. Future Extension

目前支援：

- Footwork Rule

未來可新增：

- Serve Rule
- Clear Rule
- Smash Rule
- Drive Rule
- Net Rule

新增 Rule 時，

Measurement 與 Event

不需修改。

---

# 9. Acceptance Criteria

Rule Engine V1 完成時，

需符合：

- 可分析 Return to Center
- 可分析 Recovery Time
- 可分析 Footwork Correctness
- 可分析 Body Stability
- 可輸出四項 Observation
- 可完成四項 Evaluation
- 可輸出總分
- 可輸出 Feedback Code
- 不直接產生教練文字