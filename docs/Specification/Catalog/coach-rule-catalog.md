# Coach Rule Catalog

Coach Rule 負責把 Assessment 與流程證據轉換為可解釋結果、限制與 Expert Review 建議。

## CR001 — Eight Event Completion

| 欄位 | 定義 |
|---|---|
| Rule ID | `CR001` |
| Name | `EIGHT_EVENT_COMPLETION` |
| Display Name | 八次動作完成 |
| 來源 | Event count 與 completion 狀態 |
| 可能結果 | PASS、FAIL、NEEDS_REVIEW |
| 對應 Assessment | AR001 |

## CR002 — Return To Center Completion

| 欄位 | 定義 |
|---|---|
| Rule ID | `CR002` |
| Name | `RETURN_TO_CENTER_COMPLETION` |
| Display Name | 回中心完成 |
| 來源 | 每個 Event 的 `returned_to_center` |
| 可能結果 | PASS、FAIL、NEEDS_REVIEW |
| 對應 Assessment | 目前未輸出獨立 AR object |

## CR003 — Direction Coverage

| 欄位 | 定義 |
|---|---|
| Rule ID | `CR003` |
| Name | `DIRECTION_COVERAGE` |
| Display Name | 八方向覆蓋 |
| 來源 | AR003 與 direction evidence |
| 可能結果 | PASS、NEEDS_REVIEW |
| 對應 Assessment | AR003 |

重要原則：

> `NEEDS_REVIEW` 表示系統證據不足或覆蓋不完整，不等同於使用者動作錯誤。

## CR004 — Motion Continuity

| 欄位 | 定義 |
|---|---|
| Rule ID | `CR004` |
| Name | `MOTION_CONTINUITY` |
| Display Name | 動作流程連續性 |
| 來源 | Event count validity、completed event count、pose detection rate、failure reasons |
| 可能結果 | PASS、FAIL、NEEDS_REVIEW |
| 對應 Assessment | 目前未輸出獨立 AR object |

目前不以停頓時間、碎步、啟動步或腳部時序作為判斷條件。

## CR005 — Recovery Speed

| 欄位 | 定義 |
|---|---|
| Rule ID | `CR005` |
| Name | `RECOVERY_SPEED` |
| Display Name | 回位速度 |
| 來源 | AR002 |
| 可能結果 | PASS、NEEDS_REVIEW、NOT_EVALUATED |
| 對應 Assessment | AR002 |

### Coach Overall Status

目前 Overall Status 由各 Rule 結果彙整：

- 任一 Rule 需要人工確認時，可輸出 `NEEDS_REVIEW`。
- `NEEDS_REVIEW` 不應被前端翻譯成 FAIL。
- 未評估項目不得被當成 0 分。
