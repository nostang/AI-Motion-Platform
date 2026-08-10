# Web Integration Checklist

## Environment

- [ ] API Base URL 從環境變數讀取。
- [ ] 開發環境可連線 `/openapi.json`。
- [ ] CORS origin 與實際 Web host 一致。
- [ ] 未把 `user_id`、assessment id 或本機路徑寫死。

## Upload and Camera

- [ ] 支援 MP4／MOV、3 秒下限、100 MB 上限提示。
- [ ] 延後分析原始片提示最長 120 秒。
- [ ] 直接分析提示最長 30 秒。
- [ ] Camera 30 秒自動停止，25 秒起倒數提示。
- [ ] 前端驗證失敗不送 request；Backend 錯誤仍可顯示。

## Action Window

- [ ] 使用 `defer_analysis=true` 上傳，不會立即分析。
- [ ] 使用 `/video` 播放，不讀 Backend 路徑。
- [ ] `end_ms > start_ms`，且選取片段不超過 30 秒。
- [ ] 儲存 annotation 後回首頁不重複上傳影片。
- [ ] 使用既有 assessment id 呼叫 `/analyze-annotation`。
- [ ] 發球可傳正確的 `racket_side`。

## Polling and Retry

- [ ] `completed` 與 `failed` 都會停止輪詢。
- [ ] 重複按鈕在 processing 時停用。
- [ ] 網路中斷可重試輪詢，不會重複建立任務。
- [ ] 404、409、413、422 與一般 5xx 有可理解訊息。
- [ ] 頁面重整後能由 assessment id 恢復狀態。

## Result Rendering

- [ ] 一般 UI 優先讀 `/result`。
- [ ] `null` 不會變成 0。
- [ ] Web 不重算 score、level、overall 或 Coach。
- [ ] 未完成項目顯示 `--`／「尚未完成」。
- [ ] 只有 `COMPARABLE` 才顯示前後比較。
- [ ] 人工確認持拍側有正確標籤。
- [ ] 不顯示 Backend 本機檔案路徑。

## Acceptance Scenarios

- [ ] 正常 10 秒影片：選片段、分析、開啟結果。
- [ ] 90 秒影片：延後分析可上傳，直接分析被拒絕。
- [ ] 選取超過 30 秒：被拒絕且可重新選取。
- [ ] annotation 尚未儲存：分析 API 被拒絕。
- [ ] 原始影片不存在：提供可理解的重新上傳引導。
- [ ] 分析失敗：顯示 Backend failure 並允許安全重試。
- [ ] 三項未齊：Summary 不把缺項當 0。
- [ ] 第二筆同動作：只有 Backend 判定可比較時顯示升降。
