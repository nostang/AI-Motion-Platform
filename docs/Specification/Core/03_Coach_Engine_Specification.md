# Coach Engine Specification

Version: v2.1  
Module: AI Motion  
Scope: Footwork Assessment  
Architecture Level: L3  
Status: Current

---

## 1. Purpose

Coach Engine 將 `footwork_assessment.json` 中可追溯的客觀證據，轉換為 Coach Checklist、限制說明與人工審查狀態。

Coach Engine 不重新計算 Pose、Measurement、Event 或方向分類，也不得把系統辨識不確定性直接當成使用者技術錯誤。

```text
Assessment JSON
    ↓
Coach Rules
    ↓
Coach Evaluation JSON
    ↓
Report / API / Frontend
```

## 2. Responsibility Boundary

Coach Engine 負責：

- 依據 Assessment 與流程證據執行 CR001–CR005。
- 輸出 `PASS`、`FAIL`、`NEEDS_REVIEW` 或 `NOT_EVALUATED`。
- 為每條 Rule 保存 Evidence、Explanation 與 Limitations。
- 彙整 Coach Overall Status。

Coach Engine 不負責：

- Pose Landmark 計算。
- Event 切分與方向重新分類。
- 產生沒有 Feature 或 Calibration 支撐的分數。
- 判定正式羽球等級。
- 取代真人教練診斷。

## 3. Result Semantics

| Result | Meaning |
|---|---|
| `PASS` | 現有 Evidence 足以支持該 Rule 通過 |
| `FAIL` | 現有 Evidence 明確不符合該 Rule |
| `NEEDS_REVIEW` | 有證據，但分類、覆蓋或 Calibration 仍需人工確認 |
| `NOT_EVALUATED` | 缺少 Feature、Calibration 或 Rule，尚未評估 |

`NEEDS_REVIEW` 不等於 FAIL；`NOT_EVALUATED` 不得轉成 0 分。

## 4. Current Rule Library

### CR001 — Eight Event Completion

- Evidence：detected event count、completed event count、expected event count
- PASS：剛好完成 8 個有效 Event
- 對應 Assessment：AR001 Movement Completion

### CR002 — Return To Center Completion

- Evidence：各 Event 的 `returned_to_center` 與整體回中心狀態
- PASS：所有 Event 均返回中心
- 對應 Assessment：目前尚未輸出獨立 AR object

### CR003 — Direction Coverage

- Evidence：AR003、direction coverage map、missing／duplicate directions、system confidence
- PASS：系統辨識到 8/8 預期方向
- NEEDS_REVIEW：方向缺漏、重複或分類不確定
- 對應 Assessment：AR003 Direction Coverage

### CR004 — Motion Continuity

- Evidence：event count validity、completed event count、pose detection rate、failure reasons
- 目前只評估流程是否完整連續，不評估停頓時長、碎步、啟動步或腳部時序

### CR005 — Recovery Speed

- Evidence：AR002 Recovery Speed
- 可能結果：PASS、NEEDS_REVIEW、NOT_EVALUATED
- Calibration：`recovery-speed-v1`
- 門檻為暫定版本，尚未經真人教練樣本驗證

## 5. Overall Status

優先原則：

```text
任一 FAIL              → FAIL
無 FAIL 但需人工確認   → NEEDS_REVIEW
所有已執行 Rule 通過   → PASS
沒有足夠 Rule 可判斷   → NOT_EVALUATED
```

Coach Overall Status 是 Checklist 狀態，不是羽球能力等級。

## 6. Output Contract

輸出檔案：

```text
output/coach_evaluation.json
```

每條 Rule 至少包含：

```text
rule_id
name
display_name
result
evidence
explanation
limitations
```

目前 `timing_used_for_score = true`，原因是 AR002 Recovery Speed 已正式接入評估流程。

## 7. Scope Guard

目前不評估：

- Extra Steps
- Split Step
- Lead Foot
- Dominant Hand Rule
- Body Stability Score
- Coach Similarity

新增 Coach Rule 前，必須先有可追溯 Feature、Assessment Metric、Calibration 與限制說明。
