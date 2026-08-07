# AI Motion Platform — Progress Contract V1

Version: progress-contract-v1.0

## 1. Purpose

Progress 用於比較同一位使用者、同一 Motion Type 的歷史 Assessment。

Progress 只比較已存在的 Assessment Evidence。

Progress 不預測未來表現，不修改原始 Assessment Score。

## 2. Comparison Modes

PREVIOUS
- 預設
- 與前一次同 Motion Assessment 比較

FIRST
- 與第一次同 Motion Assessment 比較

BEST
- 與歷史最高分比較
- 僅作為可選參考

CUSTOM
- 使用者指定另一筆 Assessment
- 必須為同 user_id、同 motion_type、已完成

## 3. Result

{
  "motion_type": "footwork",
  "comparison_mode": "PREVIOUS",
  "current": {
    "assessment_id": "ma_current",
    "score": 81.0
  },
  "reference": {
    "assessment_id": "ma_previous",
    "score": 77.0
  },
  "change": 4.0,
  "direction": "IMPROVED"
}

## 4. Direction

change > 0
→ IMPROVED

change = 0
→ UNCHANGED

change < 0
→ DECLINED

## 5. Version Awareness

若 model_version 或 rule_version 不一致：

comparison_status = COMPARISON_VERSION_MISMATCH

仍可顯示數值差異，
但不得直接宣稱使用者能力進步或退步。

## 6. Data Lifecycle

Video
→ 分析完成後刪除

Assessment numeric evidence
→ 保存

AI Coach text
→ 不作歷史永久資料

Training Plan text
→ 不作歷史永久資料

Progress
→ 即時計算，不永久保存

## 7. Principle

Progress describes observed change.

Progress does not predict future performance.

Every Progress conclusion must be backed by measurable Assessment evidence.
