# AI Motion Platform API Contract V3

- API version: `2.6.0`
- Prefix: `/api/v1`
- Content type: JSON，影片上傳除外
- Authentication: 目前開發版尚未提供登入／Token contract

## 1. Common Envelope

成功：

```json
{ "success": true, "data": {}, "error": null }
```

失敗：

```json
{
  "success": false,
  "data": null,
  "error": { "code": "ERROR_CODE", "message": "說明", "details": {} }
}
```

FastAPI request schema 驗證失敗可能使用標準 `422 detail[]` 格式。Client 應同時支援兩種格式。

## 2. Motion Assessment

### POST `/motion-assessments`

`multipart/form-data`：

| 欄位 | 必填 | 型別 | 說明 |
|---|---:|---|---|
| `assessment_type` | 是 | string | `footwork`、`serve`、`clear` |
| `user_id` | 是 | integer | 使用者 ID |
| `video` | 是 | binary | MP4 或 MOV，最大 100 MB |
| `client_recorded_at` | 否 | string | Client 拍攝時間 |
| `notes` | 否 | string | 備註 |
| `defer_analysis` | 否 | boolean | 預設 `false`；`true` 代表先選片段 |

回傳 `202`，`data` 至少提供 `assessment_id`、狀態資訊；延後分析時提供 `analysis_deferred=true`。直接分析最長 30 秒；延後分析原始片最長 120 秒。

### GET `/motion-assessments/{assessment_id}`

輪詢任務。主要欄位：`assessment_id`、`assessment_type`、`status`、`progress`、`current_stage`、時間欄位、`failure`；完成時可能提供 `report_url`。

Client 終止條件：`status === "completed"` 或 `status === "failed"`。不要只用 `progress === 100` 判定成功。

### GET `/motion-assessments/{assessment_id}/video`

回傳原始影片串流，供 `<video>` 播放及片段選取。Client 應以 HTTP URL 使用，不得取得或推測 Backend 本機路徑。

## 3. Human Action Window

### GET `/motion-assessments/{assessment_id}/annotation`

取得已儲存標注；不存在時依 API error 顯示「尚未選取」，不應建立假的 `0 → 0`。

### PUT `/motion-assessments/{assessment_id}/annotation`

JSON request：

```json
{
  "start_ms": 5832,
  "end_ms": 16563,
  "status": "COMPLETE",
  "motion_type": "serve",
  "action_type": "FOREHAND_SERVE",
  "racket_side": "right",
  "calibration_eligibility": "CONDITIONAL",
  "notes": "慢動作"
}
```

只有 `start_ms`、`end_ms` 必填。規則：開始不得小於 0、結束必須大於開始、片段不得超過 30 秒、結束不得超出影片容許誤差。`racket_side` 若提供，只接受 `left`／`right` 的業務值。

### POST `/motion-assessments/{assessment_id}/analyze-annotation`

以已儲存標注開始分析，回傳 `202`。沒有標注、影片不存在或任務仍在處理時會失敗。成功排隊後繼續輪詢 assessment status。

## 4. Results

### GET `/motion-assessments/{assessment_id}/result`

公開、Web 優先採用的結果 contract。適合一般結果頁、歷史紀錄及跨 Client 整合。

### GET `/motion-assessments/{assessment_id}/report`

詳細技術報告，包含 Feature、Assessment、Coach、meta、限制及分析視窗等資訊。其內部欄位會隨引擎版本演進；一般 Web 不應以內部 Feature 重算分數。

## 5. User Views

### GET `/users/{user_id}/motion-assessments?limit=20`

歷史列表。`limit` 預設 20。

### GET `/users/{user_id}/summary`

Web 能力總覽的主要來源：三項最新結果、五軸能力、前後比較及 AI 摘要。比較不成立時，Backend 會提供相應狀態；Client 不得自己挑一筆當前次。

### GET `/users/{user_id}/dashboard?limit=20`

Dashboard 聚合資料；適合需要歷史、摘要及狀態整合的頁面。

### GET `/users/{user_id}/progress/{motion_type}`

Query：`mode` 預設 `PREVIOUS`；`reference_assessment_id` 可選。用於指定動作的比較。

## 6. Advanced Generation APIs

下列端點是 Backend 能力，不代表一般 Web 必須逐一呼叫。若 `/summary` 已提供所需內容，優先使用 `/summary`。

- POST `/users/{user_id}/competency`
- POST `/users/{user_id}/coach`
- POST `/users/{user_id}/training-plan`

### POST `/competency-profiles`

### POST `/competency-profile-reports`

兩者共用 request：

```json
{
  "player_id": "1",
  "footwork_assessment_id": "ma_footwork",
  "serve_assessment_id": "ma_serve",
  "clear_assessment_id": "ma_clear"
}
```

## 7. Null、狀態與等級

- `null` 表示沒有足夠資料、未評估或不適用，不等於 0。
- 缺少的 skill 不得加入 Overall 分母。
- 等級只顯示 Backend 回傳值。
- `human_annotation_applied=true` 表示本次分析套用了人工片段。
- 人工 `racket_side` 優先，可能輸出 `dominant_hand.status=HUMAN_CONFIRMED`。

## 8. Versioning

Client 應記錄 API version，並容忍新增欄位。刪除、改名、型別或語意改變屬 breaking change，必須更新 Contract、OpenAPI、範例及整合測試。
