# AI Motion Specification v1

本目錄定義 AI Motion Platform 目前已實作的 Motion Feature、Assessment Metric、Coach Rule 與資料契約。

## 目的

- 讓 Feature、Assessment、Coach 三層責任清楚分離。
- 讓後續新增 `serve`、`clear` 等 assessment type 時可重用同一套平台結構。
- 避免在沒有資料與 Calibration 的情況下直接產生分數。
- 讓 JSON 輸出可追溯至明確的 Feature、Metric 與 Rule。

## 分層

```text
Pose Detection
    ↓
Motion Feature Library（描述資料，不評分）
    ↓
Assessment Metrics（客觀評估）
    ↓
Coach Rules（解釋、限制與審查狀態）
    ↓
Report / API / Frontend
```

## 文件

- [Motion Feature Catalog](motion-feature-catalog.md)
- [Assessment Metric Catalog](assessment-metric-catalog.md)
- [Coach Rule Catalog](coach-rule-catalog.md)
- [Contracts and Versioning](contracts-and-versioning.md)

## 當前範圍

目前正式支援：

```text
assessment_type = footwork
```

目前尚未正式支援：

```text
serve
clear
smash
```

未來新增動作類型時，應共用 API、Report 與 Validator 框架，但建立各自的 Motion、Assessment 與 Coach 規則。
