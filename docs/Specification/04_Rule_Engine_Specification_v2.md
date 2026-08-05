# Coach Engine / Rule Engine Specification

Version: v2.0  
Module: AI Motion  
Scope: Footwork Assessment  
Architecture Level: L3  
Status: Draft Approved

---

## 1. Purpose

Coach Engine 將 `footwork_assessment.json` 中的客觀事實，轉換為教練可理解、可追溯的 Coach Checklist。

Coach Engine 不重新計算 Pose、Measurement、Event 或方向分類，也不直接產生自然語言教練評論。

資料流程：

```text
Measurement
→ Footwork Event
→ Assessment JSON
→ Coach Engine
→ Coach Evaluation JSON
→ Report / Gemini / UI
```

---

## 2. Architecture Position

Assessment 描述「系統觀察到什麼」；Coach Engine 判斷「依目前教練規範，這次流程如何」。

Coach Engine 必須以 Evidence 支持每一項判斷，且不得把系統辨識不確定性誤當成使用者技術錯誤。

---

## 3. Responsibilities

Coach Engine V1 負責：

- 檢查是否剛好完成八次 Event
- 檢查每次是否返回中心
- 檢查八方向辨識覆蓋結果
- 檢查目前可觀察的流程連續性
- 為每一條規則輸出 Evidence
- 輸出 `PASS`、`FAIL` 或 `NEEDS_REVIEW`

Coach Engine V1 不負責：

- Pose 與 Landmark 計算
- Event 切分
- 調整方向分類結果
- 以速度評分
- 判斷碎步、啟動步、同手同腳
- 判定正式羽球等級
- 產生無依據的總分

---

## 4. Rule Result

固定使用：

| Result | 意義 |
| --- | --- |
| `PASS` | 現有 Evidence 足以支持通過 |
| `FAIL` | 現有 Evidence 明確不符合規範 |
| `NEEDS_REVIEW` | 系統資料不足或分類需人工確認 |
| `NOT_EVALUATED` | 本版本尚未評估 |

`NEEDS_REVIEW` 不等同於使用者做錯。

---

## 5. Rule Library V1

### CR001｜Eight Event Completion

**教練觀點**：一次米字步測驗必須剛好完成八次。少做代表未完成，多做代表流程不熟悉或不連續。

**Evidence**：

- `event_count`
- `completed_event_count`
- `expected_event_count`

**PASS**：偵測到 8 次，且 8 次均完整完成。  
**FAIL**：少於或多於 8 次，或存在未完成 Event。

### CR002｜Return to Center Completion

**教練觀點**：每次移動後都應重新返回中心，再開始下一次動作。

**Evidence**：

- 每個 Event 的 `returned_to_center`
- `all_events_returned_to_center`

**PASS**：八次皆返回中心。  
**FAIL**：至少一次未返回中心。

### CR003｜Direction Coverage

**教練觀點**：順序可不同，但八個方向必須各完成一次。

**Evidence**：

- `direction_coverage`
- `missing_directions`
- `duplicate_directions`
- `unknown_direction_count`
- `system_confidence`

**PASS**：系統辨識八方向各一次。  
**NEEDS_REVIEW**：方向缺漏、重複或不確定；需 Expert Review 確認，不能直接判定球員失敗。

### CR004｜Motion Continuity

**教練觀點**：V1 不看快慢，只看流程是否能連續完成，不應卡住、中斷或產生不完整 Event。

**Evidence**：

- `event_count_valid`
- `completed_event_count`
- Pose detection rate
- Analysis failure reasons

**PASS**：剛好 8 次、Event 均完整、Pose detection rate 足夠。  
**FAIL**：Event 次數或完整性明確不符。  
**NEEDS_REVIEW**：Pose detection rate 不足，無法可靠判斷。

---

## 6. Overall Status

優先順序：

```text
任一 FAIL          → FAIL
無 FAIL 但需複核   → NEEDS_REVIEW
四項全部 PASS      → PASS
其他               → NOT_EVALUATED
```

V1 的 `overall_status` 是 Coach Checklist 狀態，不是羽球能力等級。

---

## 7. Output

輸出檔案：

```text
output/coach_evaluation.json
```

每條 Rule 至少包含：

- Rule ID
- Rule Name
- Display Name
- Result
- Evidence
- Explanation
- Limitations

V1 明確輸出：

```json
{
  "technique_score": null,
  "timing_used_for_score": false
}
```

---

## 8. Future Extension

V2 可新增：

- CR005 Body Stability
- CR006 Extra Steps
- CR007 Split Step
- CR008 Dominant-side Lead Foot
- CR009 Footwork Sequence Quality

新增 Rule 前必須先定義教練觀點、Evidence、判定方式、限制與 Calibration 參數。

---

## 9. Acceptance Criteria

- 可讀取 Assessment JSON
- 可輸出 CR001～CR004
- 每條 Rule 都具有 Evidence
- 能區分 FAIL 與 NEEDS_REVIEW
- 不用 Recovery Time 評分
- 不產生虛假 Technique Score
- 不修改原始 Assessment JSON
- 可輸出固定 Coach Evaluation JSON
