# AI Motion API Endpoint Index

- API Version: `2.6.0`
- Base URL: `${VITE_API_BASE_URL}`，本機範例為 `http://127.0.0.1:8000/api/v1`

| Scope | Method | Path | Web 用途 |
|---|---|---|---|
| Core | POST | `/motion-assessments` | 上傳影片；直接分析或延後分析 |
| Core | GET | `/motion-assessments/{assessment_id}` | 輪詢任務狀態 |
| Window | GET | `/motion-assessments/{assessment_id}/video` | 播放已上傳影片供片段選取 |
| Window | GET | `/motion-assessments/{assessment_id}/annotation` | 讀取已儲存片段 |
| Window | PUT | `/motion-assessments/{assessment_id}/annotation` | 儲存片段及人工資訊 |
| Window | POST | `/motion-assessments/{assessment_id}/analyze-annotation` | 使用已選片段開始分析 |
| Result | GET | `/motion-assessments/{assessment_id}/result` | 公開、穩定的 Web 結果 |
| Result | GET | `/motion-assessments/{assessment_id}/report` | 詳細技術報告 |
| User | GET | `/users/{user_id}/motion-assessments?limit=20` | 歷史紀錄 |
| User | GET | `/users/{user_id}/summary` | 三項結果、雷達圖及摘要 |
| User | GET | `/users/{user_id}/dashboard?limit=20` | Dashboard 聚合資料 |
| Advanced | GET | `/users/{user_id}/progress/{motion_type}` | 單項進步比較 |
| Advanced | POST | `/users/{user_id}/competency` | 產生能力分析 |
| Advanced | POST | `/users/{user_id}/coach` | 產生教練建議 |
| Advanced | POST | `/users/{user_id}/training-plan` | 產生訓練計畫 |
| Advanced | POST | `/competency-profiles` | 指定三筆 assessment 建立能力 Profile |
| Advanced | POST | `/competency-profile-reports` | 指定三筆 assessment 建立能力報告 |

一般 Web 流程先完成 Core、Window、Result、Summary；Advanced 不必全部做成頁面。
