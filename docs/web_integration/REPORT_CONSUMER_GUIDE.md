# Report Consumer Guide

## 1. 兩種結果端點

| 端點 | 對象 | 穩定度 | 建議用途 |
|---|---|---|---|
| `/result` | 一般 Web／App | 公開 contract | 分數、等級、摘要、主要建議 |
| `/report` | 詳細報告／除錯／研究 | 技術 schema | Feature、證據、限制、引擎與校正資訊 |

新 Web 頁面先以 `/result` 實作。只有 UI 明確需要技術證據時才讀 `/report`。

## 2. 顯示規則

- 原樣呈現 Backend 的 score、level、status 與 Coach 文案。
- `null` 或缺少欄位顯示 `--`／「尚未評估」，不可顯示 0。
- `NOT_EVALUATED`、`INSUFFICIENT_DATA`、`PROVISIONAL` 等是狀態，不是低分。
- 比較只有在 Backend 表示可比較時才顯示升降。
- `comparison_status !== COMPARABLE` 時只顯示本次輪廓。
- 手別若為人工確認，顯示「右手・人工確認」或「左手・人工確認」；不要附上虛假的 100% 模型信心。

## 3. 等級

使用者結果目前分六級：

| 分數 | 等級 |
|---:|---|
| 95–100 | `EXCELLENT` |
| 90–94.999… | `WONDERFUL` |
| 80–89.999… | `GREAT` |
| 70–79.999… | `GOOD` |
| 60–69.999… | `NICE` |
| 0–59.999… | `FAIR` |

這張表供 UI 文案與測試理解，Client 仍不得由分數自行產生 level。

## 4. Meta 與追溯

技術 Report 建議保留或顯示：

- `assessment_id`
- `engine_version`
- `config_version`
- `calibration_status`
- `analysis_window`
- `human_annotation_applied`
- `limitations`

這些欄位讓問題可以追溯至使用的引擎、校正與片段。不要向一般使用者顯示 Backend 本機 `source_video` 路徑。

## 5. 慢動作與特殊影片

慢動作是影片條件，不是誤填。它可用於功能驗證與完整動作觀察，但不適合直接校正絕對速度門檻。若 Report 或 annotation notes 表示慢動作，Web 可顯示提示，不應自行修改評分。

## 6. Defensive Rendering

- 使用 optional chaining 或等價防護。
- 未知新增欄位應忽略，不應造成頁面失敗。
- 未知 enum 先顯示原值並記錄監控事件。
- 數值先確認為 finite number，再格式化。
- 技術 Report 的子結構不得假設所有 motion 完全相同。
