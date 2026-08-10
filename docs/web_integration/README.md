# AI Motion Web Integration Pack

本資料包提供給 Web 開發者及其 AI 開發工具，對應 Backend API `2.6.0`。

## 建議閱讀順序

1. `README.md`：整合範圍與文件優先順序。
2. `WEB_INTEGRATION_GUIDE.md`：Web 實作流程、狀態與責任邊界。
3. `API_CONTRACT_V3.md`：17 個 API 操作及主要資料語意。
4. `REPORT_CONSUMER_GUIDE.md`：公開結果、技術報告及空值規則。
5. `openapi.json`：機器可讀的實際路由、參數與 request schema。
6. `API_ENDPOINT_INDEX.md`：快速查表。
7. `INTEGRATION_CHECKLIST.md`：開發與驗收清單。
8. `examples/`：可複製的 request／response 範例。

## 文件優先順序

發生矛盾時，依序採用：

1. 正在運行的 Backend 行為與自動化測試。
2. 本包的 `openapi.json`。
3. `API_CONTRACT_V3.md`。
4. 其他說明及範例。

OpenAPI 目前未替所有 response 宣告完整 schema，因此 response 的業務語意仍需搭配 V3 Contract 與範例閱讀。

## Web 必做範圍

- 上傳 MP4／MOV 或使用瀏覽器錄影。
- 選取並儲存完整動作片段。
- 啟動分析、輪詢狀態、處理失敗與重試。
- 顯示公開 Result、技術 Report 與使用者 Summary。
- 保留 Backend 回傳的 `null`、狀態、分數及等級語意。

## Web 不得做的事

- 自行重算分數、等級、教練判斷或慣用手。
- 將 `null`、缺少欄位或 `NOT_EVALUATED` 自動轉成 `0`。
- 直接讀取 Backend 的 `api_data/`、`output/` 或本機路徑。
- 在 Contract 未更新前自行發明或依賴未公開欄位。
- 將技術 Report 當成穩定的公開 UI contract。

## 版本與更新

- API：`2.6.0`
- 支援動作：`footwork`、`serve`、`clear`
- 本包產生日期：`2026-08-10`

Backend 路由或欄位變更後，請重新匯出 `/openapi.json`，更新本包版本並執行整合驗收。
