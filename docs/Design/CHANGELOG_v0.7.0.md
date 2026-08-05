# AI Motion v0.7.0

## Sprint Goal

完成 Report Module。

## Completed

- 正式實作 `src/report/report_builder.py`
- 建立 Assessment + Coach Evaluation 輸入契約驗證
- 輸出 Summary、Observation、Skill Score、Feedback、Training Suggestion 與 Radar Chart Data
- Report 輸出整合至 `pose_demo.py`
- 新增 `output/footwork_analysis_report.json`
- 未完成評估的速度、技巧與身體穩定度維持 `null / NOT_EVALUATED`
- Report 不重新執行 Pose、Measurement、Event、方向分類或 Coach Rule

## Scope Guard

本版只完成 Report Module，不新增研究級演算法，不虛構尚未建立的技術分數。

## Hotfix

- 修正 `src/pose_demo.py` 誤將 `ANALYSIS_REPORT_OUTPUT_PATH` 傳入 `FootworkAssessmentBuilder.save()`，造成執行結尾出現參數數量錯誤。
- Assessment 與 Analysis Report 現在分別由各自 Builder 儲存。
