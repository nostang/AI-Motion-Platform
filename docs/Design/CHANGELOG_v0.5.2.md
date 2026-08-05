# AI Motion v0.5.2

## Added

- Coach Engine V1
- CR001 Eight Event Completion
- CR002 Return to Center Completion
- CR003 Direction Coverage
- CR004 Motion Continuity
- `output/coach_evaluation.json`
- Rule Engine Specification v2

## Design Decisions

- V1 不以速度評分。
- 方向分類不完整輸出 `NEEDS_REVIEW`，不直接判定使用者失敗。
- `technique_score` 維持 `null`。
- 每項 Coach Rule 必須附 Evidence 與限制。
