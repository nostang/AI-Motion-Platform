# AI Motion Platform --- Web Page Contract V1

**文件版本：** 1.0\
**用途：** 定義 AI Motion Platform 一般使用者 Web V1 的頁面、API
依賴、畫面狀態與前後端責任邊界。\
**前置文件：** `WEB_API_CONTRACT_V1.md`

------------------------------------------------------------------------

## 1. V1 使用者主流程

``` text
上傳頁
  ↓
建立 Motion Assessment
  ↓
分析中頁
  ↓
Assessment completed
  ↓
單項結果頁
  ↓
綜合分析頁
```

V1 核心頁面共四頁：

1.  上傳頁
2.  分析中頁
3.  單項結果頁
4.  綜合分析頁

前端負責呈現與流程控制；AI 判斷與數值解讀由後端負責。

------------------------------------------------------------------------

## 2. Page 1 --- 上傳頁

### 目的

讓使用者選擇要進行的羽球動作測驗並上傳影片。

### 支援項目

``` text
footwork → 步法
serve    → 發球
clear    → 高遠球
```

### 主要操作

-   選擇 Motion Type
-   選擇／上傳影片
-   顯示基本影片要求
-   按下「開始分析」

### API

``` http
POST /api/v1/motion-assessments
```

### 成功

取得 `assessment_id` 後進入分析中頁。

``` text
POST success
   ↓
assessment_id
   ↓
/analysis/{assessment_id}
```

### 必要狀態

**READY_TO_UPLOAD**\
使用者尚未送出影片。

**UPLOADING**\
影片正在上傳，避免重複送出。

**UPLOAD_FAILED**\
顯示後端回傳的可理解錯誤資訊，允許重新上傳。

### Web 不應做的事

-   不自行分析影片。
-   不自行判斷 Pose 品質。
-   不自行產生分數。
-   不因檔名猜測 Motion Type。

------------------------------------------------------------------------

## 3. Page 2 --- 分析中頁

### 目的

讓使用者知道影片已收到，系統正在分析，而不是畫面卡住。

### API

``` http
GET /api/v1/motion-assessments/{assessment_id}
```

### 畫面至少顯示

-   分析狀態
-   Motion Type
-   可用時顯示目前處理階段或進度
-   分析中的明確提示

### 狀態流程

``` text
processing
    ↓
completed
    ↓
單項結果頁
```

若後端回傳失敗狀態：

``` text
failed
  ↓
顯示錯誤
  ↓
允許回上傳頁重新操作
```

### Completed 行為

完成後導向：

``` text
/result/{assessment_id}
```

並由結果頁取得 Presentation Result。

### 原則

前端不得根據等待時間猜測分析是否成功或失敗；以 Assessment API
回傳狀態為準。

------------------------------------------------------------------------

## 4. Page 3 --- 單項結果頁

### 目的

呈現「這一次影片」的使用者可理解結果。

### API

``` http
GET /api/v1/motion-assessments/{assessment_id}/result
```

### 必顯示內容

``` text
Motion Label
Score / Max Score
Presentation Level
Breakdown
```

### 範例

``` text
步法分析

77 / 100
GOOD

移動完成度    25 / 25
回位速度      18 / 25
動作流暢度    22 / 25
身體穩定度    12 / 25
```

### Level

前端直接使用後端 `level`：

``` text
FAIR
NICE
GOOD
GREAT
WONDERFUL
EXCELLENT
```

Web 不重新依分數計算 Level。

### Breakdown

Web 使用：

``` text
key
label
score
max_score
```

畫面應優先顯示後端提供的 `label`，不要在前端建立另一份評分名稱規則。

### 建議操作

-   返回上傳／測驗入口
-   查看綜合分析

### Technical Detail

一般使用者頁不直接顯示：

-   raw features
-   MediaPipe landmarks
-   calibration
-   Rule Engine evidence
-   internal model/rule versions

若未來需要技術分析頁，另建立 Technical Detail UI，不塞進一般結果頁。

------------------------------------------------------------------------

## 5. Page 4 --- 綜合分析頁

### 目的

讓使用者理解目前三項羽球動作的整體狀態，而不是只看到單次影片。

### API

``` http
GET /api/v1/users/{user_id}/summary
```

### 頁面區塊

建議依序呈現：

``` text
A. Player Context
B. 三項 Motion Summary
C. Radar Chart
D. Progress
E. AI Summary
F. Training Recommendations
```

------------------------------------------------------------------------

## 6. Player Context 區塊

V1 顯示持拍手：

``` text
持拍手：右手
```

來源：

``` json
{
  "racket_hand": {
    "status": "ESTIMATED",
    "estimated": "right",
    "confidence": 0.85,
    "source_motion": "clear"
  }
}
```

### 顯示規則

``` text
right   → 右手
left    → 左手
unknown → 尚無法判斷
```

若 `status` 不可用或 `estimated = unknown`，不得自行猜測。

Confidence 可視 UI 需求決定是否對一般使用者顯示；資料仍保留在 Contract
中供系統解釋使用。

------------------------------------------------------------------------

## 7. Motion Summary 區塊

V1 顯示三項：

``` text
步法
發球
高遠球
```

範例：

``` text
步法      77  GOOD
發球      74  GOOD
高遠球    86  GREAT
```

每項資料直接使用 Summary API：

``` text
assessment_id
motion_type
label
score
max_score
level
progress
```

------------------------------------------------------------------------

## 8. Progress 顯示

V1 比較同一 Motion 的前一次 Assessment。

### Direction 對應

``` text
IMPROVED  → 進步
DECLINED  → 下降
UNCHANGED → 持平
```

例如：

``` text
步法  77  GOOD  持平
```

或：

``` text
步法  82  GREAT  +5
```

### 注意

若：

``` text
comparison_status != COMPARABLE
```

Web 不應顯示「進步」或「退步」結論。

應改顯示：

``` text
目前無法直接比較
```

後端負責版本相容性判斷，前端不自行比較兩次分數。

------------------------------------------------------------------------

## 9. Radar Chart 區塊

直接使用：

``` json
{
  "labels": ["步法", "發球", "高遠球"],
  "scores": [77.0, 74.0, 86.0],
  "max_score": 100.0
}
```

Web 只負責繪圖。

不得：

-   從其他 API 重新組一套 Radar Score。
-   自行加權三項分數。
-   產生 Cross-Motion Overall Score。

目前平台明確不計算三項綜合總分。

------------------------------------------------------------------------

## 10. AI Summary 區塊

### 建議畫面

``` text
AI 分析

高遠球目前是相對優勢項目，分數為 86 分。

三項目前皆與前一次持平。

優先改善
步法、發球
```

資料來源：

``` text
headline
progress_summary
focus
recommendations
```

### Recommendations

範例：

``` text
優先加強步法穩定、回位與動作一致性。
優先加強發球穩定性與揮拍流暢度。
高遠球目前為優勢項目，可維持技術並持續提升穩定性。
```

Web 不修改推薦邏輯，也不根據分數自行產生建議。

------------------------------------------------------------------------

## 11. Summary 不完整狀態

使用者可能尚未完成全部三項測驗。

Summary API 已提供：

``` text
missing_motions
```

### UI 行為

例如缺少 Clear：

``` text
尚未完成：高遠球

完成三項測驗後，
即可查看完整綜合分析。
```

可以顯示目前已完成項目，但不可把不完整資料包裝成完整 Competency 結論。

------------------------------------------------------------------------

## 12. 共用頁面狀態

V1 Web 應明確處理以下狀態。

### Loading

正在取得 API 資料。

### Ready

資料完整，可正常呈現。

### Empty

使用者尚無相關 Assessment。

### Incomplete

已有部分資料，但不足以產生完整結果。

### Failed

分析或 API 請求失敗。

### Not Comparable

Progress 存在，但因版本或證據條件不適合直接解讀。

前端不應把上述狀態全部統一顯示成「系統錯誤」。

------------------------------------------------------------------------

## 13. Error UX 原則

錯誤訊息應回答：

``` text
發生什麼事？
使用者現在可以做什麼？
```

例如影片資料不足：

``` text
目前無法完成動作判斷。

請確認人物完整入鏡、畫面清楚，
並重新錄製後再試一次。
```

不應只顯示：

``` text
Error 409
```

但前端也不應自行發明失敗原因；原因必須來自後端可支持的資訊。

------------------------------------------------------------------------

## 14. Web 與 Backend 責任邊界

### Web 可以做

-   Layout
-   Responsive UI
-   Loading Animation
-   Error / Empty State
-   Score 視覺呈現
-   Breakdown Bar
-   Progress Icon
-   Radar Chart
-   AI Summary 排版
-   頁面跳轉

### Web 不可以做

-   重算 Score
-   重算 Level
-   重算 Progress
-   推導持拍手
-   修改 Coach Recommendation
-   從 raw features 產生新結論
-   自行判斷使用者正式羽球程度
-   預測未來表現

核心原則：

> Web 顯示後端可解釋的結果，不創造新的評估事實。

------------------------------------------------------------------------

## 15. Technical Detail 與 Expert Review

這兩者不屬於一般使用者 V1 四頁流程。

### Technical Detail

用途：

``` text
查看 Features
查看 Evidence
查看 Confidence
查看 Limitations
Debug / Validation
```

原則：Read Only。

### Expert Review

用途：

``` text
教練／資深球友查看影片
確認 AI 判斷
修正或補充人工標籤
留下人工覆核紀錄
```

AI 原始結果與 Expert Review 必須分開保存。

Expert Review 不應靜默覆寫原始 AI Assessment。

------------------------------------------------------------------------

## 16. Web Optional 頁面

以下不是 V1 核心四頁，但現有 API 已支援未來擴充。

### 歷史紀錄

``` http
GET /api/v1/users/{user_id}/motion-assessments
```

可建立「我的分析紀錄」。

### Dashboard

``` http
GET /api/v1/users/{user_id}/dashboard
```

適合帳號首頁顯示：

-   完成分析次數
-   平均分數
-   最近 Motion
-   最近分數
-   歷史最佳 Motion
-   歷史最佳分數
-   Competency 是否已具備三項資料
-   Recent Analyses

Dashboard 與 Summary 定位不同：

``` text
Dashboard → 我使用平台的歷史概況
Summary   → 我目前三項動作能力的分析結果
```

------------------------------------------------------------------------

## 17. V1 頁面與 API 對照

  Page         API                                     類型
  ------------ --------------------------------------- --------------
  上傳頁       `POST /motion-assessments`              Web Core
  分析中頁     `GET /motion-assessments/{id}`          Web Core
  單項結果頁   `GET /motion-assessments/{id}/result`   Web Core
  綜合分析頁   `GET /users/{id}/summary`               Web Core
  歷史紀錄     `GET /users/{id}/motion-assessments`    Web Optional
  Dashboard    `GET /users/{id}/dashboard`             Web Optional

------------------------------------------------------------------------

## 18. V1 完成定義

Web V1 在以下流程可以完整走通時，即具備 Demo 基準：

``` text
選擇 Motion
→ 上傳影片
→ 建立 Assessment
→ 等待分析
→ 完成
→ 顯示單項 Result
→ 查看 Summary
→ 顯示三項分數 / Level
→ 顯示 Progress
→ 顯示 Radar
→ 顯示 Player Context
→ 顯示 AI Summary / Recommendations
```

V1 不要求：

-   Expert Review UI
-   Technical Detail UI
-   更多 Motion
-   正式羽球程度分級
-   比賽／Rally 能力推論
-   未來表現預測

上述項目屬於後續版本。
