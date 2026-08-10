# Prompt for Web Development AI

將以下內容連同本資料夾全部文件交給 Web 開發 AI：

```text
你正在整合 AI Motion Platform Backend API 2.6.0。

請先完整閱讀：
1. README.md
2. WEB_INTEGRATION_GUIDE.md
3. API_CONTRACT_V3.md
4. REPORT_CONSUMER_GUIDE.md
5. openapi.json
6. INTEGRATION_CHECKLIST.md

工作規則：
- 先說明你理解的頁面流程、API 呼叫順序與資料 mapping，再開始改 code。
- API Base URL 必須來自環境變數，不可寫死。
- 一般結果頁優先使用 /result；只有技術細節使用 /report。
- 不得自行計算 score、level、overall、比較結果、Coach 或慣用手。
- null、缺少欄位及 NOT_EVALUATED 不得轉成 0。
- 不得讀取或依賴 Backend 的 api_data、output 或本機路徑。
- 所有 request 必須有 Loading、Empty、Error、Retry 與 Completed 狀態。
- 若文件與實際 OpenAPI 衝突，停止實作並列出衝突，不要自行猜欄位。
- 每完成一個流程，依 INTEGRATION_CHECKLIST.md 逐項驗證並回報證據。

第一個里程碑請只完成：
上傳／錄影 → 選取動作片段 → 儲存 annotation → 啟動分析 → 輪詢 → 顯示公開 result。
不要一開始就實作所有 Advanced endpoints。
```

若要新增頁面，先複製 `WEB_IMPLEMENTATION_SPEC_TEMPLATE.md` 並填完，再要求 AI 實作。
