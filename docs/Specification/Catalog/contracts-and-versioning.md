# Contracts and Versioning

## Current Versions

| Contract | Version |
|---|---|
| Footwork Assessment Schema | `1.3` |
| Motion Feature Library | `motion-feature-v1` |
| Recovery Speed Calibration | `recovery-speed-v1` |
| Direction Coverage Calibration | `direction-coverage-v1` |
| Coach Engine | `1.0` |
| Analysis Report | `1.0` |
| Motion Engine | `0.5.1` |
| Footwork Calibration | `footwork-calibration-v1` |

## Status Semantics

### `EVALUATED`

資料足夠，且已執行目前版本的 Assessment Rule。

### `NOT_EVALUATED`

目前沒有足夠 Feature、Calibration 或 Rule。不得以 0 分取代。

### `NEEDS_REVIEW`

系統已產生證據，但存在覆蓋不足、分類不確定或 Calibration 尚待人工驗證的情況。不得直接解讀為 FAIL。

### `PASS`

符合目前版本的明確規則。只代表該 Rule 的範圍，不代表完整技術能力。

### `FAIL`

不符合目前版本的明確規則。必須同時提供 evidence 與 limitations。

## Score Contract

完整 `overall_score` 只有在四個 Skill Score 全部完成時才能產生：

```text
Movement Completion
Recovery Speed
Footwork Technique
Body Stability
```

若有任何一項 `NOT_EVALUATED`：

```text
overall_score = null
```

部分完成時可輸出：

```text
evaluated_score
evaluated_max_score
score_coverage
```

Direction Coverage 屬於獨立 `assessment_metrics`，不直接併入 100 分技術總分。

## Feature Contract

Motion Feature 必須保存：

```text
feature_version
status
sample_count
valid_sample_count
valid_sample_ratio
phase_samples
time_range_ms
pose_quality
features
limitations
```

Feature 不得直接產生 PASS、FAIL 或技術分數。

## Extension Contract

未來新增動作類型時，建議維持：

```text
assessment_type = footwork | serve | clear | ...
```

共用：

```text
Upload API
Task Status API
Report API
Repository
Validator framework
Frontend shell
```

各動作類型自行提供：

```text
Motion/Event definition
Feature selection
Assessment metrics
Coach rules
Report mapping
Calibration version
```

## Breaking Changes

下列變更需要升級 API 或 Schema Version：

- 刪除或重新命名既有 JSON 欄位。
- 改變 Status 的語意。
- 改變分數最大值或總分組成。
- 改變 assessment type 的必要輸入。
- 將原本 `NOT_EVALUATED` 的欄位強制改成數值。

新增可選欄位通常可維持同一 API version，但應升級 Assessment Schema Version。
