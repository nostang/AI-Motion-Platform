# AI Motion Platform --- Camera Recording Contract V1

**文件版本：** 1.0\
**階段：** Camera Recording V1.1\
**用途：** 定義 Web
現場錄影功能的流程、畫面狀態、前後端邊界與驗收條件。\
**相關文件：** `WEB_API_CONTRACT_V1.md`、`WEB_PAGE_CONTRACT_V1.md`

------------------------------------------------------------------------

## 1. 目標

Camera Recording V1.1 讓使用者除了上傳既有影片，也能直接從 Web
開啟裝置鏡頭，完成錄影後送入既有 AI Motion Assessment Pipeline。

V1.1 **不是即時 AI 動作分析**。

核心流程：

``` text
Camera
→ Recording
→ Video File / Blob
→ POST /motion-assessments
→ Existing Backend Pipeline
→ Result
```

後端正式評分流程維持不變。

------------------------------------------------------------------------

## 2. 使用者流程

``` text
選擇 Motion
   ↓
選擇影片來源
   ├─ 上傳影片
   └─ 現場錄影
         ↓
      Camera Permission
         ↓
      Camera Preview
         ↓
      Guide Overlay
         ↓
       3 / 2 / 1
         ↓
         REC
         ↓
       結束錄影
         ↓
       Video Preview
      ↙             ↘
  重新錄影          送出分析
                       ↓
             POST /motion-assessments
                       ↓
                  分析中頁
                       ↓
                  單項結果頁
```

------------------------------------------------------------------------

## 3. Camera Preview

Camera Preview 應包含三層：

``` text
Camera <video>
      +
Guide <svg>
      +
UI Overlay <div>
```

### Guide Overlay

V1.1 使用靜態人體引導圖，不做 Pose 判斷。

示意：

``` text
┌──────────────────────────┐
│                          │
│           ○              │
│          /|\             │
│           |              │
│          / \             │
│                          │
│   請將全身保持在框線內     │
│                          │
│       [ 開始錄影 ]         │
└──────────────────────────┘
```

引導圖只協助構圖，不代表系統已確認人體符合分析條件。

------------------------------------------------------------------------

## 4. 拍攝指引

V1.1 可顯示靜態提示：

``` text
請保持全身入鏡
請將裝置固定
避免逆光或過暗
動作期間不要離開畫面
```

這些是拍攝建議，不應顯示成 AI 已驗證的 `✓`。

例如 V1.1 不應宣稱：

``` text
✓ 全身已完整入鏡
✓ 光線品質合格
```

除非後續 Camera Readiness Engine 已實際完成對應檢查。

------------------------------------------------------------------------

## 5. Camera Permission 狀態

### REQUESTING_PERMISSION

正在要求瀏覽器 Camera 權限。

### READY

Camera 已成功開啟，可預覽。

### PERMISSION_DENIED

顯示：

``` text
無法使用相機。

請允許瀏覽器使用相機，
或改用「上傳影片」完成測驗。
```

### CAMERA_UNAVAILABLE

裝置沒有可使用的 Camera，或 Camera 無法初始化。

應保留「上傳影片」作為替代路徑。

------------------------------------------------------------------------

## 6. 錄影狀態

建議狀態：

``` text
IDLE
COUNTDOWN
RECORDING
RECORDED
UPLOADING
FAILED
```

### IDLE

Camera Preview 已開啟，等待開始。

### COUNTDOWN

``` text
3
2
1
```

倒數期間尚未開始正式錄影。

### RECORDING

畫面清楚顯示：

``` text
● REC
00:05
[ 結束錄影 ]
```

### RECORDED

停止 Camera Recording，顯示錄製影片預覽。

操作：

``` text
[ 重新錄影 ]
[ 送出分析 ]
```

### UPLOADING

錄製影片正在送入 Assessment API。

禁止重複送出。

------------------------------------------------------------------------

## 7. 錄影技術邊界

Web 可使用瀏覽器：

``` text
navigator.mediaDevices.getUserMedia()
MediaRecorder
```

取得 Camera Stream 並錄製成 Blob。

概念流程：

``` text
getUserMedia
   ↓
MediaStream
   ↓
MediaRecorder
   ↓
Recorded Chunks
   ↓
Blob
   ↓
File / FormData
   ↓
POST /motion-assessments
```

Web 不在此階段解析 Motion Score。

------------------------------------------------------------------------

## 8. Video Format

瀏覽器實際可錄製格式可能依裝置與瀏覽器不同。

因此前端不得假設所有環境都固定輸出 `.mp4`。

實作時應：

1.  使用瀏覽器支援的 MediaRecorder MIME type。
2.  保留實際 MIME type。
3.  上傳前確認 Backend 接受該格式。
4.  若 Backend 不接受，應在前後端交接層處理格式相容性，而不是修改 AI
    Assessment 邏輯。

### V1.1 特別注意

目前 Backend Contract
支援的影片格式與瀏覽器錄製格式必須在實作階段進行相容性驗證。

這是 Camera Recording V1.1 的必要 Integration Check。

------------------------------------------------------------------------

## 9. 錄影長度

應遵守既有 Assessment API 的影片長度限制。

Web 可在錄影 UI：

-   顯示錄影秒數。
-   到達最大時間時自動停止。
-   太短時阻止送出並提供提示。

真正的 API 驗證仍由 Backend 負責，前端限制只是 UX 防呆，不取代後端驗證。

------------------------------------------------------------------------

## 10. Motion Type

使用者在開啟 Camera 前應已選擇：

``` text
footwork
serve
clear
```

錄影完成後，Motion Type 與 Video 一起送入既有：

``` http
POST /api/v1/motion-assessments
```

Camera Recording 不建立新的 Assessment Endpoint。

------------------------------------------------------------------------

## 11. 重新錄影

使用者按下：

``` text
重新錄影
```

應：

1.  捨棄目前尚未送出的 Recording Blob。
2.  返回 Camera Preview。
3.  不建立 Assessment。
4.  不保留上一段影片作為正式分析證據。

只有使用者按下「送出分析」後才建立 Assessment。

------------------------------------------------------------------------

## 12. Upload Hand-off

Camera Recording 的責任終點：

``` text
成功取得可上傳影片
```

之後完全交給既有 Web / API 流程：

``` text
Recorded Video
   ↓
POST /motion-assessments
   ↓
assessment_id
   ↓
分析中頁
   ↓
GET /motion-assessments/{id}
   ↓
completed
   ↓
GET /motion-assessments/{id}/result
```

Camera Recording 不建立第二套分析 Pipeline。

------------------------------------------------------------------------

## 13. V1.1 不做的功能

以下不屬於 Camera Recording V1.1：

``` text
即時 Pose Detection
即時動作評分
即時 Coach Feedback
自動判斷全身入鏡
自動判斷人物距離
自動判斷主要關節可見度
自動判斷動作是否正確
```

這些不得由靜態 Overlay 假裝已完成。

------------------------------------------------------------------------

## 14. Camera Readiness V1.2

下一階段可在錄影前加入 Pose-based Input Quality Gate。

目標不是評分，而是回答：

``` text
「目前畫面是否適合開始錄影？」
```

候選檢查：

``` text
人體是否存在
主要關節是否可見
頭部是否在畫面內
腳踝是否在畫面內
人物是否過大
人物是否過小
```

UI 可以依真實檢查結果顯示：

``` text
請站入畫面
請往後站
請靠近一些
✓ 全身主要關節可見
✓ 可以開始錄影
```

------------------------------------------------------------------------

## 15. Readiness 與 Assessment 邊界

必須維持：

``` text
Camera Readiness
→ Input Quality Gate
→ 不評分

Backend Assessment
→ Official Motion Analysis
→ Score / Level / Breakdown
```

Readiness 結果不得：

-   修改正式 Score。
-   取代正式 Pose Pipeline。
-   推導正式 Motion Level。
-   宣稱動作正確。
-   成為第二套 Rule Engine。

------------------------------------------------------------------------

## 16. Failure UX

### Permission Denied

提供重新授權說明與「上傳影片」替代入口。

### Recording Failed

``` text
錄影未完成，請重新嘗試。
```

不得建立 Assessment。

### Upload Failed

保留目前錄影，若技術上可行應允許再次送出，避免要求使用者立刻重錄。

### Backend Rejected Video

顯示 Backend 支持的原因與下一步指引。

例如資料不足時，應引導使用者改善拍攝條件，而不是自行推測動作問題。

------------------------------------------------------------------------

## 17. Privacy / Camera UX

Camera 僅在需要 Preview / Recording 時啟用。

離開 Camera 頁面或不再需要 Camera 時，Web 應停止 MediaStream
tracks，避免鏡頭持續使用。

錄影尚未送出前，不應被視為正式 Assessment。

UI 應清楚區分：

``` text
正在預覽
正在錄影
錄影完成但尚未送出
已送出分析
```

------------------------------------------------------------------------

## 18. V1.1 驗收條件

Camera Recording V1.1 完成需至少通過：

``` text
[ ] 可以選擇「現場錄影」
[ ] 可以要求 Camera Permission
[ ] Camera Preview 正常
[ ] 靜態人體 Guide Overlay 正常
[ ] 有拍攝指引
[ ] 有 3-2-1 Countdown
[ ] 可以開始錄影
[ ] 可以停止錄影
[ ] 顯示 Recording Timer
[ ] 可以預覽錄製影片
[ ] 可以重新錄影
[ ] 可以送出分析
[ ] 錄影影片成功進入既有 POST /motion-assessments
[ ] 成功取得 assessment_id
[ ] 可以進入既有分析中頁
[ ] 分析完成後可以進入既有 Result
[ ] Camera Permission 被拒絕時仍可改走上傳影片
[ ] 離開 Camera 後 Camera Stream 正確停止
[ ] 已驗證實際瀏覽器錄影格式與 Backend 格式相容性
```

------------------------------------------------------------------------

## 19. V1.1 完成後架構

``` text
                   AI Motion Web
                        │
              ┌─────────┴─────────┐
              │                   │
         Upload Video        Record Camera
              │                   │
              └─────────┬─────────┘
                        │
                    Video File
                        │
                        ▼
             POST /motion-assessments
                        │
                        ▼
                Existing Backend
                        │
         Pose → Feature → Assessment
                        │
                        ▼
                      Result
```

Camera Recording 是新的 **Input Method**，不是新的 AI Engine。

------------------------------------------------------------------------

## 20. 後續版本

``` text
V1.1
Camera Recording
+ Static Guide Overlay

V1.2
Camera Readiness
+ Pose-based Input Quality Gate

V2+
視需求評估 Real-time Motion Analysis
```

優先順序：

> 先確保使用者能穩定取得可分析的影片，再考慮即時分析。
