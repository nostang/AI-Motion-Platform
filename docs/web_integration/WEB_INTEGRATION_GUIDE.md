# AI Motion Web Integration Guide

## 1. 目標流程

推薦採用「先上傳、選片段、再分析」：

1. 使用者選擇 `footwork`、`serve` 或 `clear`。
2. 上傳影片時呼叫 `POST /motion-assessments`，傳入 `defer_analysis=true`。
3. 取得 `assessment_id` 後，以 `/video` 在片段選取頁播放影片。
4. 使用者設定開始與結束時間，呼叫 `PUT /annotation`。
5. 返回首頁顯示檔名及「已選片段」，但不要重新上傳同一支影片。
6. 按下開始分析後呼叫 `POST /analyze-annotation`。
7. 輪詢 `GET /motion-assessments/{id}`，直到 `completed` 或 `failed`。
8. 完成後讀取 `/result` 顯示公開結果；需要技術細節時才讀 `/report`。

直接分析仍受支援：上傳時傳 `defer_analysis=false`，Backend 會直接排入分析，不進入片段選取流程。

## 2. 時間與檔案限制

| 情境 | 限制 |
|---|---|
| 格式 | `.mp4`、`.mov` |
| 檔案大小 | 最大 100 MB |
| 最短影片 | 3 秒 |
| 直接分析影片 | 最長 30 秒 |
| 延後分析的原始影片 | 最長 120 秒 |
| 人工選取片段 | 最長 30 秒，且 `end_ms > start_ms` |
| 瀏覽器錄影 | 3–30 秒；30 秒自動停止 |

前端驗證只用於 UX；Backend 驗證仍是最終依據。原始影片暫時保留供選取片段與重新分析，正式清理週期尚未定案，因此 Web 不應承諾永久保存。

## 3. 前端狀態

建議 UI 狀態：

`idle → uploading → selecting → annotation_saved → queued → processing → completed | failed`

- `sessionStorage` 只能協助同一分頁回首頁後恢復 `assessment_id` 與片段；不能當永久資料庫。
- 重新整理後應嘗試由 URL 或已保存的 assessment id 恢復，再向 API 查真實狀態。
- `processing` 時停用重複送出。
- 網路錯誤與分析 `failed` 必須分開呈現；網路錯誤可重試輪詢，不代表分析失敗。

## 4. 人工標注

最少只需傳 `start_ms` 與 `end_ms`。發球或高遠球建議同時提供：

- `action_type`：例如 `FOREHAND_SERVE`。
- `racket_side`：`left` 或 `right`。
- `calibration_eligibility`：校正資料用途，普通使用者 UI 可省略。
- `notes`：例如慢動作、重播或特殊拍攝角度。

人工填寫的持拍側優先於系統推估。報告可能顯示「右手・人工確認」，並保留自動估計作稽核資訊；Web 不得自行改回自動結果。

## 5. 錯誤處理

業務錯誤通常使用：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ANNOTATION_REQUIRED",
    "message": "請先選取並儲存完整動作區間。",
    "details": {}
  }
}
```

前端顯示優先順序：`error.message → detail → message → HTTP status fallback`。常見情況包括影片過大、過長、片段超出影片、尚未儲存片段、任務處理中及原始影片不存在。

## 6. 前端責任邊界

前端負責輸入、導覽、Loading、錯誤、重試、資料呈現與可及性。Backend 負責動作辨識、Feature、Assessment、分數、等級、Coach、比較與報告。

等級以 Backend 為準：`FAIR`、`NICE`、`GOOD`、`GREAT`、`WONDERFUL`、`EXCELLENT`。沒有結果時顯示 `--` 或「尚未完成」，不可顯示 `0`。

## 7. 環境設定

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

不得把 Base URL、使用者 ID、assessment id 或 Backend 檔案路徑寫死在元件內。
