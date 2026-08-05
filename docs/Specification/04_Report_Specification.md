# Report Specification

Version: v1.0  
Module: AI Motion  
Scope: Footwork Assessment  
Architecture Level: L3  
Status: Draft Approved

---

# 1. Purpose

Report Layer 的目的，是將 Rule Engine 的分析結果整理成統一的分析資料模型（Analysis Report）。

Report Layer 不重新計算任何技術數值。

Report Layer 僅負責：

- 整理分析結果
- 統一資料格式
- 提供 Feedback 與 Training Suggestion
- 提供 UI 顯示所需資料

資料流程：

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
↓
Web / LINE / PDF
```

---

# 2. Responsibilities

Report Layer 負責：

✅ 整理 Rule Engine 輸出

✅ 建立統一 Report Model

✅ 提供所有 UI 共用資料

✅ 轉換 Feedback Code

✅ 提供訓練建議

---

Report Layer 不負責：

❌ Measurement

❌ Event 判定

❌ Rule 評分

❌ Landmark 計算

❌ UI 排版

---

# 3. Report Structure

第一版 Report 包含：

1. Summary
2. Observation
3. Skill Score
4. Coach Feedback
5. Training Suggestion
6. Radar Chart Data

---

# 4. Summary

Summary 提供本次分析摘要。

包含：

- Motion
- Analysis Time
- Completed
- Overall Score

Example：

```text
Motion

Footwork

Completed

YES

Overall Score

86
```

---

# 5. Observation

Observation 為 Rule Engine 的分析結果。

不包含任何主觀評論。

第一版 Observation：

| Observation | Result |
|-------------|--------|
| Return Center | PASS |
| Recovery Time | 0.82 sec |
| Footwork Correctness | PASS |
| Body Stability | PASS |

Observation 為所有後續分析的基礎。

---

# 6. Skill Score

Skill Score 為四項技術評估結果。

第一版：

| Item | Score |
|------|------:|
| Movement Completion | 25 / 25 |
| Recovery Speed | 18 / 25 |
| Footwork Technique | 23 / 25 |
| Body Stability | 20 / 25 |

Total

```text
86 / 100
```

---

# 7. Coach Feedback

Coach Feedback 根據 Feedback Code

轉換為固定建議。

第一版：

| Code | Feedback |
|------|----------|
| F001 | 尚未完全回到中心位置。 |
| F002 | 回中心速度可再提升。 |
| F003 | 動作中出現多餘碎步。 |
| F004 | 腳步順序需要調整。 |
| F005 | 回中心時身體穩定性不足。 |

第一版採固定文字。

第二版可導入 LLM 產生自然語言建議。

---

# 8. Training Suggestion

Training Suggestion 根據 Observation 與 Feedback Code

提供訓練方向。

Example：

Recovery Speed 偏低：

```text
建議加強米字步回中心練習。

每組 20 次。

共 5 組。
```

Footwork Technique 偏低：

```text
建議先降低移動速度。

確認腳步順序正確。

再逐漸增加速度。
```

第一版採固定建議。

第二版可依不同程度推薦不同課表。

---

# 9. Radar Chart Data

Radar Chart 不由 Report 計算。

Report 僅提供畫圖資料。

Example：

```json
{
    "labels":[
        "Movement Completion",
        "Recovery Speed",
        "Footwork Technique",
        "Body Stability"
    ],

    "scores":[
        25,
        18,
        23,
        20
    ]
}
```

任何 UI 可直接使用此資料繪製雷達圖。

---

# 10. Report JSON Schema

Report Layer 最終輸出的資料格式如下：

```json
{
  "motion": "Footwork",

  "completed": true,

  "overall_score": 86,

  "observation": {

    "return_center": true,

    "recovery_time": 0.82,

    "footwork_correct": true,

    "body_stable": true

  },

  "skill_score": {

    "movement_completion": 25,

    "recovery_speed": 18,

    "footwork_technique": 23,

    "body_stability": 20

  },

  "feedback": [

    "F002",

    "F003"

  ],

  "training": [

    "Recovery Drill",

    "Footwork Drill"

  ],

  "radar_chart": {

    "labels":[

      "Movement Completion",

      "Recovery Speed",

      "Footwork Technique",

      "Body Stability"

    ],

    "scores":[25,18,23,20]

  }
}
```

此 JSON 為 Report Layer 與 UI Layer 的資料契約（Data Contract）。

任何前端（Web、LINE Bot、PDF、Mobile App）皆應以此格式取得分析結果。

---

# 11. UI Independence

Report Layer 不依賴任何 UI Framework。

Report 可提供：

- Web Dashboard
- LINE Bot
- PDF Report
- Coach Dashboard
- Mobile App

所有 UI 共用同一份 Report Data。

不得因不同 UI 而修改 Report 結構。

---

# 12. Future Extension

第二版可新增：

- AI 自然語言分析
- 歷史分析
- 多次訓練趨勢
- 成長曲線
- 教練留言
- 分享報告
- PDF 匯出
- 雲端同步

---

# 13. Acceptance Criteria

Report V1 完成時，

需符合：

- 可輸出 Summary
- 可輸出 Observation
- 可輸出 Skill Score
- 可輸出 Coach Feedback
- 可輸出 Training Suggestion
- 可提供 Radar Chart Data
- 可輸出固定 JSON Schema
- 不重新計算任何 Rule
- 不依賴任何 UI