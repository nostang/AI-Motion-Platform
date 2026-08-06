# AI Motion API Contract

Version: v1.0  
Module: AI Motion  
Current Assessment Type: `footwork`  
Status: Implemented MVP

---

## 1. Purpose

本文件定義 Frontend 或其他模組如何建立分析任務、查詢狀態與取得 Report。外部呼叫端不需要理解 MediaPipe、Event Engine、Assessment 或 Coach Engine 的內部實作。

## 2. Base URL

本機開發：

```text
http://127.0.0.1:8000/api/v1
```

Swagger：

```text
http://127.0.0.1:8000/docs
```

正式部署網域尚未在本專案中定案。

## 3. Authentication

目前本機 MVP 尚未實作 Authentication。未來若整合共用 Backend、LINE Login 或會員系統，需另行升級 API Contract。

## 4. Supported Assessment Types

| assessment_type | Status |
|---|---|
| `footwork` | Implemented |
| `serve` | Future |
| `clear` | Future |
| `smash` | Future |

未支援類型回傳 `INVALID_ASSESSMENT_TYPE`。

## 5. Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/motion-assessments` | 上傳影片並建立分析任務 |
| GET | `/motion-assessments/{assessment_id}` | 查詢任務狀態 |
| GET | `/motion-assessments/{assessment_id}/report` | 取得 Analysis Report |

## 6. Create Motion Assessment

```http
POST /api/v1/motion-assessments
Content-Type: multipart/form-data
```

### Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `assessment_type` | string | Yes | 目前固定為 `footwork` |
| `video` | file | Yes | MP4 或 MOV |
| `client_recorded_at` | string | No | ISO 8601 |
| `notes` | string | No | 備註 |

### Success

```http
202 Accepted
```

```json
{
  "success": true,
  "data": {
    "assessment_id": "ma_xxx",
    "assessment_type": "footwork",
    "status": "uploaded",
    "created_at": "...",
    "status_url": "/api/v1/motion-assessments/ma_xxx",
    "report_url": "/api/v1/motion-assessments/ma_xxx/report"
  },
  "error": null
}
```

## 7. Get Assessment Status

```http
GET /api/v1/motion-assessments/{assessment_id}
```

目前主要狀態：

```text
uploaded
processing
completed
failed
```

Response 另包含 `progress`、`current_stage`、timestamps 與 `failure`。

## 8. Get Report

```http
GET /api/v1/motion-assessments/{assessment_id}/report
```

成功時回傳 Report v1.0 envelope，內容包含 Summary、Observation、Skill Score、Assessment Metrics、Radar Chart、Review 與 Meta。

## 9. Standard Response Envelope

成功：

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

失敗：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

## 10. Current Constraints

- 僅支援 Footwork Assessment。
- 本機 API 與 Frontend 使用不同 port 時，需要 CORS middleware。
- 分析任務目前以檔案型 Repository 保存。
- Authentication、雲端儲存與正式部署不在目前 MVP 範圍。
