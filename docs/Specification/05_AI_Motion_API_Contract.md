# AI Motion API Contract

Version: v1.0  
Module: AI Motion  
Scope: Footwork Assessment  
Architecture Level: L3  
Status: Draft Approved

---

## 1. Purpose

本文件定義 AI Motion 模組與下列模組之間的 API 資料契約：

- Web Frontend
- LINE Bot
- 共用 Backend
- AI Motion Engine

本文件的目的，是確保所有模組使用相同的：

- API 路徑
- Request 格式
- Response 格式
- 狀態代碼
- 錯誤格式
- Report JSON Schema

前端與 LINE Bot 不需要理解：

- MediaPipe Pose
- Measurement
- Footwork Event
- Rule Engine

前端與 LINE Bot 只需要依照本文件：

1. 建立分析任務
2. 查詢分析狀態
3. 取得分析結果
4. 呈現 Report Data

---

## 2. Architecture Boundary

AI Motion 對外資料流程：

```text
Web / LINE Bot
↓
Common Backend API
↓
AI Motion Engine
↓
Report JSON
↓
Web / LINE Bot
```

AI Motion Engine 內部流程：

```text
Video
↓
MediaPipe Pose
↓
Measurement
↓
Footwork Event
↓
Rule Engine
↓
Report
```

Web 與 LINE Bot 不得直接呼叫：

- MediaPipe
- Measurement
- Event
- Rule Engine

所有外部模組皆透過共用 Backend API 存取 AI Motion。

---

## 3. Base URL

開發環境：

```text
http://localhost:8000/api/v1
```

正式環境：

```text
https://{GCP_SERVICE_DOMAIN}/api/v1
```

正式 GCP 網域於部署完成後補入。

---

## 4. Authentication

所有需要會員身份的 API，使用：

```http
Authorization: Bearer <access_token>
```

第一版 Token 由共用 Backend 驗證。

AI Motion Engine 不自行處理 LINE Login 或 LIFF Login。

若 Token：

- 未提供
- 已失效
- 無法驗證

API 回傳：

```http
HTTP 401 Unauthorized
```

---

## 5. Supported Assessment Types

第一版只支援：

| assessment_type | 說明 | MVP 狀態 |
| --- | --- | --- |
| `footwork` | 米字步標準化測驗 | ✅ 支援 |
| `serve` | 反手發小球測驗 | Future |
| `clear` | 高遠球動作測驗 | Future |

若傳入未支援的 Assessment Type，回傳：

```http
HTTP 400 Bad Request
```

---

## 6. Analysis Status

分析任務狀態固定使用下列值：

| Status | 說明 |
| --- | --- |
| `uploaded` | 影片已上傳，尚未開始處理 |
| `validating` | 正在檢查影片品質 |
| `queued` | 已通過檢查，等待分析 |
| `processing` | 正在進行 AI Motion 分析 |
| `completed` | 分析完成，可取得報告 |
| `failed` | 分析失敗 |
| `rejected` | 影片未通過品質檢查 |

前端不得自行新增其他狀態文字。

畫面顯示文字可自行翻譯，但程式判斷必須使用上述固定值。

---

# 7. API Endpoints

第一版包含三個核心 API：

| Method | Endpoint | 用途 |
| --- | --- | --- |
| `POST` | `/motion-assessments` | 建立分析任務並上傳影片 |
| `GET` | `/motion-assessments/{assessment_id}` | 查詢任務狀態 |
| `GET` | `/motion-assessments/{assessment_id}/report` | 取得分析報告 |

---

# 8. Create Motion Assessment

## Endpoint

```http
POST /api/v1/motion-assessments
```

## Purpose

建立一次 AI Motion 標準化測驗，並上傳待分析影片。

## Content Type

```http
multipart/form-data
```

## Request Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `assessment_type` | string | Yes | 第一版固定為 `footwork` |
| `video` | file | Yes | 使用者上傳的測驗影片 |
| `client_recorded_at` | string | No | 使用者裝置錄影時間，ISO 8601 |
| `notes` | string | No | 測試或開發備註 |

## Request Example

```bash
curl -X POST \
  "http://localhost:8000/api/v1/motion-assessments" \
  -H "Authorization: Bearer <access_token>" \
  -F "assessment_type=footwork" \
  -F "video=@footwork.mov" \
  -F "client_recorded_at=2026-08-04T10:20:00+08:00"
```

## Success Response

```http
HTTP 202 Accepted
```

```json
{
  "success": true,
  "data": {
    "assessment_id": "ma_01J4ABCDEF123456",
    "assessment_type": "footwork",
    "status": "uploaded",
    "created_at": "2026-08-04T10:21:15+08:00",
    "status_url": "/api/v1/motion-assessments/ma_01J4ABCDEF123456",
    "report_url": "/api/v1/motion-assessments/ma_01J4ABCDEF123456/report"
  },
  "error": null
}
```

## Notes

此 API 使用 `202 Accepted`，代表：

> 系統已接受分析任務，但分析不一定已完成。

前端不得在收到此 Response 後直接假設已有分數。

---

# 9. Get Motion Assessment Status

## Endpoint

```http
GET /api/v1/motion-assessments/{assessment_id}
```

## Purpose

查詢 AI Motion 分析任務目前狀態。

## Path Parameter

| Parameter | Type | Description |
| --- | --- | --- |
| `assessment_id` | string | 建立任務時取得的唯一 ID |

## Processing Response

```http
HTTP 200 OK
```

```json
{
  "success": true,
  "data": {
    "assessment_id": "ma_01J4ABCDEF123456",
    "assessment_type": "footwork",
    "status": "processing",
    "progress": 65,
    "current_stage": "event_detection",
    "created_at": "2026-08-04T10:21:15+08:00",
    "updated_at": "2026-08-04T10:21:42+08:00",
    "completed_at": null,
    "failure": null
  },
  "error": null
}
```

## Completed Response

```json
{
  "success": true,
  "data": {
    "assessment_id": "ma_01J4ABCDEF123456",
    "assessment_type": "footwork",
    "status": "completed",
    "progress": 100,
    "current_stage": "completed",
    "created_at": "2026-08-04T10:21:15+08:00",
    "updated_at": "2026-08-04T10:22:03+08:00",
    "completed_at": "2026-08-04T10:22:03+08:00",
    "report_url": "/api/v1/motion-assessments/ma_01J4ABCDEF123456/report",
    "failure": null
  },
  "error": null
}
```

## Rejected Response

影片品質檢查未通過時，Status 使用 `rejected`：

```json
{
  "success": true,
  "data": {
    "assessment_id": "ma_01J4ABCDEF123456",
    "assessment_type": "footwork",
    "status": "rejected",
    "progress": 100,
    "current_stage": "video_validation",
    "created_at": "2026-08-04T10:21:15+08:00",
    "updated_at": "2026-08-04T10:21:21+08:00",
    "completed_at": "2026-08-04T10:21:21+08:00",
    "failure": {
      "code": "VIDEO_FULL_BODY_NOT_VISIBLE",
      "message": "影片未完整拍攝到受測者全身。",
      "retryable": true
    }
  },
  "error": null
}
```

---

# 10. Get Motion Assessment Report

## Endpoint

```http
GET /api/v1/motion-assessments/{assessment_id}/report
```

## Purpose

取得已完成的 AI Motion 分析報告。

## Success Condition

只有任務狀態為：

```text
completed
```

才可取得報告。

## Success Response

```http
HTTP 200 OK
```

```json
{
  "success": true,
  "data": {
    "assessment_id": "ma_01J4ABCDEF123456",
    "assessment_type": "footwork",
    "report_version": "1.0",
    "analyzed_at": "2026-08-04T10:22:03+08:00",

    "summary": {
      "motion": "footwork",
      "completed": true,
      "overall_score": 86
    },

    "observation": {
      "return_center": true,
      "recovery_time": 0.82,
      "footwork_correct": true,
      "extra_steps": 1,
      "body_stable": true
    },

    "skill_score": {
      "movement_completion": {
        "score": 25,
        "max_score": 25
      },
      "recovery_speed": {
        "score": 18,
        "max_score": 25
      },
      "footwork_technique": {
        "score": 23,
        "max_score": 25
      },
      "body_stability": {
        "score": 20,
        "max_score": 25
      }
    },

    "feedback": [
      {
        "code": "F002",
        "message": "回中心速度可再提升。"
      },
      {
        "code": "F003",
        "message": "動作中出現多餘碎步。"
      }
    ],

    "training_suggestions": [
      {
        "code": "T001",
        "title": "回中心練習",
        "description": "加強米字步回中心練習。",
        "sets": 5,
        "repetitions_per_set": 20
      },
      {
        "code": "T002",
        "title": "腳步順序練習",
        "description": "先降低移動速度，確認腳步順序正確後再逐漸加速。",
        "sets": null,
        "repetitions_per_set": null
      }
    ],

    "radar_chart": {
      "labels": [
        "Movement Completion",
        "Recovery Speed",
        "Footwork Technique",
        "Body Stability"
      ],
      "scores": [
        25,
        18,
        23,
        20
      ],
      "max_score": 25
    },

    "meta": {
      "model_name": "MediaPipe Pose Landmarker",
      "measurement_version": "1.0",
      "event_version": "1.0",
      "rule_version": "1.0",
      "video_retention_status": "temporary"
    }
  },
  "error": null
}
```

---

# 11. Report Not Ready

若任務尚未完成：

```http
HTTP 409 Conflict
```

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "REPORT_NOT_READY",
    "message": "分析尚未完成，暫時無法取得報告。",
    "details": {
      "assessment_id": "ma_01J4ABCDEF123456",
      "status": "processing"
    }
  }
}
```

---

# 12. Standard Response Envelope

所有 API Response 必須使用相同外層格式。

## Success

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

## Failure

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "提供給使用者或開發者的錯誤訊息。",
    "details": {}
  }
}
```

前端不得依賴非固定格式的純文字錯誤。

---

# 13. Error Codes

| HTTP Status | Error Code | 說明 |
| --- | --- | --- |
| 400 | `INVALID_ASSESSMENT_TYPE` | 不支援的測驗類型 |
| 400 | `VIDEO_REQUIRED` | 未提供影片 |
| 400 | `INVALID_VIDEO_FORMAT` | 不支援的影片格式 |
| 400 | `VIDEO_TOO_LONG` | 影片超過允許長度 |
| 401 | `UNAUTHORIZED` | 未登入或 Token 無效 |
| 403 | `FORBIDDEN` | 無權存取該分析紀錄 |
| 404 | `ASSESSMENT_NOT_FOUND` | 找不到分析任務 |
| 409 | `REPORT_NOT_READY` | 分析尚未完成 |
| 413 | `VIDEO_TOO_LARGE` | 影片檔案過大 |
| 422 | `VIDEO_FULL_BODY_NOT_VISIBLE` | 全身未完整入鏡 |
| 422 | `VIDEO_LOW_VISIBILITY` | Landmark 辨識可信度不足 |
| 422 | `VIDEO_DURATION_INVALID` | 影片長度不符合規範 |
| 500 | `ANALYSIS_FAILED` | AI Motion 分析失敗 |
| 503 | `SERVICE_UNAVAILABLE` | 分析服務暫時無法使用 |

---

# 14. Video Constraints

第一版影片限制暫定如下：

| 項目 | 規則 |
| --- | --- |
| 支援格式 | `.mp4`、`.mov` |
| 最大檔案大小 | 100 MB |
| 最長影片時間 | 30 秒 |
| 最短影片時間 | 3 秒 |
| 人數 | 一次只允許一位受測者 |
| 畫面要求 | 全身與雙腳完整入鏡 |
| 建議解析度 | 1080p |
| 建議 FPS | 30 FPS 以上 |
| 拍攝方向 | 依 Assessment Guide 與 ACS 規範 |

以上數值皆為 MVP 暫定值，可於 PoC 後調整。

---

# 15. Frontend Polling Rule

建立分析任務後，Web 或 LINE Bot 可定期查詢狀態。

第一版建議：

```text
每 2 秒查詢一次
```

當 Status 為下列任一值時停止查詢：

- `completed`
- `failed`
- `rejected`

不得在 Status 為 `processing` 時請求並顯示假分數。

---

# 16. Frontend Display Mapping

前端可將 API Status 轉換為以下顯示文字：

| API Status | 建議顯示文字 |
| --- | --- |
| `uploaded` | 影片上傳完成 |
| `validating` | 正在檢查影片 |
| `queued` | 等待分析中 |
| `processing` | AI 動作分析中 |
| `completed` | 分析完成 |
| `failed` | 分析失敗 |
| `rejected` | 影片不符合規範 |

前端可調整文案，但不得改變原始 Status 值。

---

# 17. LINE Bot Usage

LINE Bot 不直接接收或解析 Measurement。

LINE Bot 可使用：

```http
GET /motion-assessments/{assessment_id}
```

查詢分析狀態。

分析完成後使用：

```http
GET /motion-assessments/{assessment_id}/report
```

取得 Report。

LINE Bot 建議呈現：

- Overall Score
- 四項 Skill Score
- 前兩項 Feedback
- Web 詳細報告連結

若 Report 尚未完成，不得自行推測結果。

---

# 18. Web Frontend Usage

Web Frontend 可使用 Report Response 呈現：

- 總分卡片
- Observation 表格
- 四項技術分數
- Radar Chart
- Coach Feedback
- Training Suggestion

Web Frontend 不得：

- 重新計算 Overall Score
- 重新判定 PASS / FAIL
- 自行產生 Feedback Code
- 修改 Rule Engine 結果

---

# 19. Data Ownership and Access

每筆 Motion Assessment 必須綁定：

- `assessment_id`
- `user_id`
- `assessment_type`
- `created_at`

使用者只能查詢自己的分析紀錄。

教練或管理員存取權限屬於 Future Scope，MVP 不開放任意查看其他會員影片或報告。

---

# 20. Idempotency and Duplicate Submission

第一版暫不要求完整 Idempotency Key。

前端必須在送出分析任務後停用重複提交按鈕，避免短時間內建立重複任務。

Future 可支援：

```http
Idempotency-Key: <unique_key>
```

---

# 21. Versioning

API 路徑使用：

```text
/api/v1
```

Report 另外包含：

```json
{
  "report_version": "1.0",
  "measurement_version": "1.0",
  "event_version": "1.0",
  "rule_version": "1.0"
}
```

Rule 或 Report 格式有重大變更時，必須更新版本。

---

# 22. AI Coding Instructions

將本文件提供給程式生成 AI 時，必須附上以下指示：

```text
請嚴格依照本 API Contract 開發。

不得自行：
1. 修改 Endpoint 名稱
2. 修改 JSON 欄位名稱
3. 新增未定義的 Status
4. 在前端重新計算 AI Motion 分數
5. 將假資料當成正式分析結果
6. 略過 Standard Response Envelope
7. 將 Measurement 或 Rule 邏輯放入前端

若規格中有未定義內容，請先列出待確認事項，不要自行猜測。
```

---

# 23. Acceptance Criteria

AI Motion API Contract V1 實作完成時，需符合：

- 可建立 Footwork Assessment
- 可上傳影片
- 可取得唯一 `assessment_id`
- 可查詢固定分析狀態
- 可取得完整 Report JSON
- 所有 Response 使用標準外層格式
- 所有 Error 使用固定 Error Code
- Web 與 LINE Bot 不重新計算分數
- 未完成分析不得回傳正式 Report
- API 與 Report 均有版本資訊
- 使用者不得讀取他人的分析紀錄