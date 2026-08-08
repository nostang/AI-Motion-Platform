# AI Motion Platform --- Web API Contract V1

**文件版本：** 1.0\
**對應 API：** v2.6.0\
**用途：** 定義一般 Web 前端可依賴的 API 與資料邊界。\
**原則：** 前端負責呈現；評分、Level、Progress、Competency 與 Coach
判斷由後端負責。

------------------------------------------------------------------------

## 1. Contract 目標

AI Motion Platform 內部包含
Vision、Feature、Assessment、Rule、Progress、Competency、Coach
等多層能力。\
Web 前端不應重新實作這些判斷，而應使用後端提供的 Presentation API。

主要資料流：

``` text
Video
  ↓
Vision / Pose
  ↓
Features
  ↓
Assessment / Rules
  ↓
Progress / Competency / Coach
  ↓
Presentation Contract
  ├─ /result
  └─ /summary
  ↓
Web
```

------------------------------------------------------------------------

## 2. API 分類

### A. Web Core --- 一般使用流程

  ------------------------------------------------------------------------------------------------------
  Method                  Endpoint                                              用途
  ----------------------- ----------------------------------------------------- ------------------------
  POST                    `/api/v1/motion-assessments`                          上傳影片並建立分析任務

  GET                     `/api/v1/motion-assessments/{assessment_id}`          查詢分析任務狀態

  GET                     `/api/v1/motion-assessments/{assessment_id}/result`   取得單項 Presentation
                                                                                Result

  GET                     `/api/v1/users/{user_id}/summary`                     取得使用者綜合分析
  ------------------------------------------------------------------------------------------------------

這四支是 Web V1 的核心依賴。

### B. Web Optional --- 歷史與 Dashboard

  ----------------------------------------------------------------------------------------------
  Method                  Endpoint                                       用途
  ----------------------- ---------------------------------------------- -----------------------
  GET                     `/api/v1/users/{user_id}/motion-assessments`   使用者歷史分析紀錄

  GET                     `/api/v1/users/{user_id}/dashboard`            Dashboard 資料
  ----------------------------------------------------------------------------------------------

是否使用由前端頁面需求決定。

### C. Backend Capability --- 平台能力

  -----------------------------------------------------------------------------------------------------
  Method                  Endpoint                                           用途
  ----------------------- -------------------------------------------------- --------------------------
  POST                    `/api/v1/competency-profiles`                      由指定 Assessment 建立
                                                                             Competency Profile

  POST                    `/api/v1/competency-profile-reports`               建立 Competency Profile
                                                                             Report

  POST                    `/api/v1/users/{user_id}/competency`               依使用者最新三項結果建立
                                                                             Competency

  POST                    `/api/v1/users/{user_id}/coach`                    產生 AI Coach 結果

  POST                    `/api/v1/users/{user_id}/training-plan`            產生訓練計畫

  GET                     `/api/v1/users/{user_id}/progress/{motion_type}`   單項歷史比較
  -----------------------------------------------------------------------------------------------------

這些 API 保留獨立能力與測試用途。一般 Summary
頁不需要自行呼叫它們再拼裝結果。

### D. Technical Detail --- 技術分析資料

  -----------------------------------------------------------------------------------------------------
  Method                  Endpoint                                              用途
  ----------------------- ----------------------------------------------------- -----------------------
  GET                     `/api/v1/motion-assessments/{assessment_id}/report`   完整 Report / Features
                                                                                / Evidence 等技術資料

  -----------------------------------------------------------------------------------------------------

此 API 不屬於一般使用者 Presentation Contract。

### E. Expert Review --- 未來擴充

Expert Review 與 Technical Detail 是不同概念。

-   **Technical Detail：** Read Only，查看系統實際
    Features、Evidence、Confidence、Limitations 等。
-   **Expert Review：**
    未來由教練／資深球友確認或修正標籤，人工覆核結果應與 AI
    原始結果分開保存。
-   Expert Review 不應靜默覆寫原始 AI Assessment。

------------------------------------------------------------------------

## 3. 單項結果 Contract

### Endpoint

``` http
GET /api/v1/motion-assessments/{assessment_id}/result
```

### 用途

使用者完成一項影片分析後，取得適合直接呈現在 Web 的單項結果。

### Response 範例 --- Footwork

``` json
{
  "success": true,
  "data": {
    "assessment_id": "ma_c1a053ad4f4d4385",
    "motion_type": "footwork",
    "status": "READY",
    "score": 77.0,
    "max_score": 100.0,
    "level": "GOOD",
    "breakdown": [
      {
        "key": "movement_completion",
        "label": "移動完成度",
        "score": 25.0,
        "max_score": 25.0
      },
      {
        "key": "recovery_speed",
        "label": "回位速度",
        "score": 18.0,
        "max_score": 25.0
      },
      {
        "key": "motion_quality",
        "label": "動作流暢度",
        "score": 22.0,
        "max_score": 25.0
      },
      {
        "key": "body_stability",
        "label": "身體穩定度",
        "score": 12.0,
        "max_score": 25.0
      }
    ]
  },
  "error": null
}
```

### Level

Level 由後端決定，Web 不自行換算。

目前 Presentation Level 包含：

``` text
FAIR
NICE
GOOD
GREAT
WONDERFUL
EXCELLENT
```

其中已確定：

``` text
90–94  WONDERFUL
95–100 EXCELLENT
```

前端應直接顯示 API 回傳的 `level`。

------------------------------------------------------------------------

## 4. 綜合分析 Contract

### Endpoint

``` http
GET /api/v1/users/{user_id}/summary
```

### 用途

提供綜合分析頁需要的單一 Presentation Payload，包括：

-   Player Context
-   三項最新結果
-   前一次比較
-   Radar Chart
-   AI Summary
-   Missing Motions

### Response 結構

``` json
{
  "success": true,
  "data": {
    "status": "READY",
    "player_context": {},
    "motions": [],
    "radar_chart": {},
    "missing_motions": [],
    "ai_summary": {}
  },
  "error": null
}
```

------------------------------------------------------------------------

## 5. Player Context

目前 V1 提供持拍手：

``` json
{
  "player_context": {
    "racket_hand": {
      "status": "ESTIMATED",
      "estimated": "right",
      "confidence": 0.85,
      "source_motion": "clear"
    }
  }
}
```

### 規則

-   `racket_hand` 是影片層級 Context，不參與評分。
-   Web 不得由 raw Features 自行推導持拍手。
-   V1 來源為最新 Clear Report 的 `features.racket_hand`。
-   `estimated` 可為 `right`、`left` 或 `unknown`。
-   若未來多項影片皆能估算持拍手，發生互相衝突時應回傳明確 conflict
    狀態，不應由前端猜測。

`racket_side_estimate` 屬於 Analyzer 內部計算上下文，不作為正式 Player
Context。

------------------------------------------------------------------------

## 6. Motion Summary

每個 Motion 提供：

``` json
{
  "assessment_id": "ma_c1a053ad4f4d4385",
  "motion_type": "footwork",
  "label": "步法",
  "score": 77.0,
  "max_score": 100.0,
  "level": "GOOD",
  "progress": {
    "status": "READY",
    "previous_score": 77.0,
    "change": 0.0,
    "direction": "UNCHANGED",
    "comparison_status": "COMPARABLE"
  }
}
```

V1 必要 Motion：

``` text
footwork → 步法
serve    → 發球
clear    → 高遠球
```

------------------------------------------------------------------------

## 7. Progress Contract

Summary V1 僅比較同一 Motion 的**前一筆 Assessment**。

### Direction

``` text
IMPROVED  → 本次分數較前一次高
DECLINED  → 本次分數較前一次低
UNCHANGED → 本次與前一次同分
```

同分是合法且明確的結果：

``` json
{
  "previous_score": 77.0,
  "change": 0.0,
  "direction": "UNCHANGED"
}
```

### Version Safety

若 Model Version 或 Rule Version
不一致，後端可保留數值差異，但不應直接解讀為進步或退步。

前端應尊重 `comparison_status`，不自行重新判斷。

------------------------------------------------------------------------

## 8. Radar Chart

Web 直接使用後端提供的 Radar 資料：

``` json
{
  "radar_chart": {
    "labels": ["步法", "發球", "高遠球"],
    "scores": [77.0, 74.0, 86.0],
    "max_score": 100.0
  }
}
```

前端只負責繪圖，不重新計算分數。

------------------------------------------------------------------------

## 9. AI Summary

範例：

``` json
{
  "ai_summary": {
    "status": "READY",
    "headline": "高遠球目前是相對優勢項目，分數為 86 分。",
    "progress_summary": "三項目前皆與前一次持平。",
    "focus": ["步法", "發球"],
    "recommendations": [
      "優先加強步法穩定、回位與動作一致性。",
      "優先加強發球穩定性與揮拍流暢度。",
      "高遠球目前為優勢項目，可維持技術並持續提升穩定性。"
    ],
    "evidence": {
      "strengths": [],
      "improvement_priorities": []
    }
  }
}
```

AI Summary 必須基於既有 Assessment / Competency / Coach / Progress
證據產生。

它不應：

-   重新評分。
-   預測未來表現。
-   在證據不足時自行補完事實。
-   將單一動作測驗解讀為正式羽球程度分級。

------------------------------------------------------------------------

## 10. Web 不應自行處理的資料

一般 Web Presentation 不應依賴：

``` text
MediaPipe landmarks
raw feature measurements
Rule Engine evidence
calibration values
model/rule internal versions
完整 Coach internal evidence
Analyzer internal racket_side_estimate
```

需要除錯或驗證時，應使用 Technical Detail /
Report，而不是把工程資料耦合進一般 UI。

------------------------------------------------------------------------

## 11. Web V1 建議流程

``` text
1. 使用者上傳影片
   POST /motion-assessments

2. Web 取得 assessment_id

3. 查詢分析狀態
   GET /motion-assessments/{assessment_id}

4. completed
   ↓

5. 顯示單項結果
   GET /motion-assessments/{assessment_id}/result

6. 使用者進入綜合分析頁
   GET /users/{user_id}/summary
```

Web 不需要為 Summary 頁另外呼叫 Competency、Coach、Progress、Training
Plan 再自行組裝。

------------------------------------------------------------------------

## 12. Presentation / Backend Responsibility

### Backend 負責

-   Motion Analysis
-   Score
-   Level
-   Breakdown
-   Progress
-   Player Context
-   Competency
-   Coach Interpretation
-   AI Summary
-   Evidence consistency

### Web 負責

-   畫面與互動
-   Loading / Error / Empty State
-   Score / Level 呈現
-   Breakdown 呈現
-   Progress 圖示與文字呈現
-   Radar Chart 繪製
-   AI Summary 呈現

**Web 顯示結果，不重新定義結果。**

------------------------------------------------------------------------

## 13. V1 邊界

目前 Contract 以三項 Motion 為核心：

-   Footwork
-   Forehand Serve
-   High Clear

未來新增 Motion 時，後端可擴充 Presentation Payload；Web
不應假設永遠只有固定的內部 Feature 欄位。

Expert Review、Technical Detail UI 與多影片持拍手一致性判斷不屬於本版
Web Contract 的核心範圍。
