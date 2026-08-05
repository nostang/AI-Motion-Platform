# CHANGELOG v0.8.0

## Module

Pipeline Validator Module

## Added

- `src/validator/pipeline_validator.py`
- `src/validator/validation_rules.py`
- `src/validator/__init__.py`
- `output/pipeline_validation.json`

## Validation Scope

- Assessment 必要欄位、型別、Event 數量與 Event ID
- Coach Evaluation 必要欄位、Rule Result、Rule ID 與 Checklist 統計
- Analysis Report 必要欄位、Coach Status 與 Radar Chart 契約
- Expert Review Package 必要欄位、Review Status 與 Event 結構
- 跨模組 `assessment_id`
- 跨模組 `assessment_type`
- 跨模組 `engine_version`
- 跨模組 `config_version`
- Coach Status 與 Report Coach Status
- Assessment Event 與 Review Package Event 的順序與 ID

## Pipeline Integration

Validator 於 Assessment、Coach、Report、Review Package 全部輸出後執行。
若 Contract 驗證失敗，主流程會拋出 `PipelineValidationError`，避免把不一致輸出視為成功結果。

## Non-goals

- 不重新計算 Motion 或 Coach 結果
- 不新增評分演算法
- 不修改 Calibration
- 不修改既有 JSON 的業務判斷

## Hotfix 2026-08-05

- 修正 `src/pose_demo.py` 呼叫 `ReportBuilder.save()` 時誤傳入 `PIPELINE_VALIDATION_OUTPUT_PATH` 的參數錯誤。
- Report 與 Pipeline Validation 現在各自使用正確的 Builder 儲存至獨立輸出路徑。
