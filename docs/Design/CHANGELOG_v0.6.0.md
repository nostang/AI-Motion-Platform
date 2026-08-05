# AI Motion v0.6.0

## Sprint Goal

完成 Coach Module。

## Added

- 正式建立 `src/coach/coach_engine.py`
- 正式建立 `src/coach/coach_rules.py`
- Coach Rule Library：CR001～CR004
- Assessment 最小輸入契約驗證
- `output/coach_evaluation.json`
- Coach Evaluation 儲存流程

## Fixed

- `pose_demo.py` 原本引用舊的 `src.rule.coach_engine`
- `pose_demo.py` 原本印出未建立的 `coach_evaluation`
- Coach 實作位置與正式 Module 目錄不一致

## Compatibility

- `src/rule/coach_engine.py` 保留為舊 import 相容層
- Coach Module 的唯一正式實作位於 `src/coach/`

## Scope

本版只完成 Coach Module，不新增技術分數、速度評分或研究級演算法。
