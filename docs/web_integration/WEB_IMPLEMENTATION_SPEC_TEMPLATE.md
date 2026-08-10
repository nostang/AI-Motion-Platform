# Web Feature Specification Template

> 每一個新頁面或流程複製本模板。先填清楚 contract，再交給 AI 寫程式。

## Feature

- 名稱：
- 目的：
- 使用者：
- 對應設計稿／Issue：
- API version：`2.6.0`

## User Flow

1. 
2. 
3. 

## API Dependencies

| Method | Endpoint | 觸發時機 | 成功後動作 |
|---|---|---|---|
| | | | |

## Input Contract

| 欄位 | 型別 | 必填 | 驗證 | UI 來源 |
|---|---|---:|---|---|
| | | | | |

## Output Mapping

| API JSON path | UI 元件 | `null` 顯示 | 格式 |
|---|---|---|---|
| | | | |

## States

- Idle：
- Loading：
- Empty：
- Success：
- Recoverable error：
- Terminal error：

## Error Mapping

| HTTP／error.code | 使用者訊息 | 可否重試 | 動作 |
|---|---|---:|---|
| | | | |

## Non-goals

- 不自行計算 Backend 的分數、等級或 Coach。
- 不直接讀取 Backend filesystem。
- 

## Acceptance Criteria

- [ ] 
- [ ] `null`、空資料與失敗狀態已測試。
- [ ] Keyboard、手機版與 Loading 狀態已測試。
- [ ] API request／response 已用 Network panel 驗證。

## Test Cases

| Case | Given | When | Then |
|---|---|---|---|
| Happy path | | | |
| Empty/null | | | |
| Validation error | | | |
| Network retry | | | |
