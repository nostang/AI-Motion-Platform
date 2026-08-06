# Analysis Report Specification

Version: v1.2  
Module: AI Motion  
Scope: Footwork Assessment  
Architecture Level: L3  
Status: Current

---

## 1. Purpose

Report Layer 將 Assessment、Coach Evaluation 與相關 Metadata 整理成固定的 Analysis Report Contract，供 API、Frontend 與後續整合使用。

Report Layer 不重新計算 Pose、Event、Feature 或 Coach Rule，也不得為未評估項目虛構數值。

## 2. Current Report Sections

1. Summary
2. Observation
3. Skill Score
4. Assessment Metrics
5. Feedback
6. Training Suggestions
7. Radar Chart Data
8. Review
9. Meta

## 3. Summary

目前包含：

```text
motion
completed
overall_score
evaluated_score
evaluated_max_score
score_coverage
coach_status
```

### Overall Score Contract

完整 `overall_score` 只有在下列四個 Skill Score 全部完成時才可產生：

```text
Movement Completion
Recovery Speed
Footwork Technique
Body Stability
```

若任一項是 `NOT_EVALUATED`：

```text
overall_score = null
```

部分完成時，使用：

```text
evaluated_score
evaluated_max_score
score_coverage
```

## 4. Observation

目前可包含：

- Return to Center
- Recovery Time statistics
- Motion Continuity
- Direction Coverage status
- Missing Directions
- System Confidence

未完成評估的 `footwork_correct`、`extra_steps`、`body_stable` 維持 `null`。

## 5. Skill Score

目前四個固定 Skill Score：

| Item | Current Status |
|---|---|
| Movement Completion | EVALUATED |
| Recovery Speed | EVALUATED |
| Footwork Technique | NOT_EVALUATED |
| Body Stability | NOT_EVALUATED |

`NOT_EVALUATED` 不得以 0 取代。

## 6. Assessment Metrics

Direction Coverage 為獨立測驗覆蓋指標：

```text
assessment_metrics.direction_coverage
```

此指標不直接併入完整 100 分技術總分。

## 7. Feedback and Training Suggestions

目前 Contract 保留：

```text
feedback
training_suggestions
```

現階段可為空陣列。Report 不得自行生成沒有 Coach Rule 或訓練規格支撐的建議。

## 8. Radar Chart

目前固定維度：

```text
Movement Completion
Recovery Speed
Direction Coverage
Footwork Technique
Body Stability
```

未評估值輸出 `null`，Frontend 必須顯示為未評估，不得畫成 0 分。

## 9. Review

Review 應保存：

- `recommended`
- `needs_review_count`
- `limitations`

目前 Direction Coverage 與 Recovery Speed 的 Calibration 限制必須保留於 Report。

## 10. Meta

目前至少保存：

```text
model_name
assessment_schema_version
engine_version
config_version
coach_engine_version
timing_used_for_score
not_evaluated
```

## 11. Scope Guard

Report 不負責：

- 重新執行分析流程。
- 將 Direction Coverage 誤當完整 Footwork Technique。
- 將 2D Motion Feature 直接轉成 Body Stability 分數。
- 產生無依據的 Overall Score、Feedback 或 Training Suggestion。
