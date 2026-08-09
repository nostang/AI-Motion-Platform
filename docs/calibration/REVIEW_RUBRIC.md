# AI Motion 人工評閱規則 V1

## 目的

先由人工觀察影片，再與系統輸出比較。

本階段驗證的是：

1. 系統是否看見影片中明顯的優缺點。
2. 分數高低順序是否符合人工觀察。
3. 是否受到環境、角度或偵測失敗誤導。

本階段不追求教練級精密分數，也不直接修改 Calibration。

## 評閱順序

1. 不查看系統報告，完整觀看影片。
2. 填寫環境與拍攝角度。
3. 判斷各項動作維度。
4. 填寫人工整體等級、優勢與問題。
5. 執行系統分析並抄錄結果。
6. 判斷人工與系統是否一致。

## 共用人工標記

### 各維度

- CLEAR：影片中明確完成或表現良好。
- PARTIAL：有做到，但不完整或不穩定。
- NOT_OBSERVED：沒有觀察到。
- NOT_JUDGABLE：拍攝角度、遮擋或畫面品質不足，無法判斷。

### 整體等級

- GOOD：主要動作清楚完成，只有輕微問題。
- FAIR：動作可辨識，但有一項以上明顯問題。
- POOR：主要動作未完成，或多項問題明顯。
- NOT_JUDGABLE：影片條件不足，人工也無法可靠判斷。

## 步法 Footwork

依序觀察：

1. movement_completion：是否完成預期步法流程。
2. recovery_speed：移動後是否能及時回位。
3. direction_coverage：是否涵蓋預期方向。
4. motion_quality：移動是否流暢，沒有明顯卡頓。
5. body_stability：移動與回位時軀幹是否穩定。

填寫範例：

`movement_completion=CLEAR; recovery_speed=PARTIAL; direction_coverage=CLEAR; motion_quality=PARTIAL; body_stability=POOR`

## 正手發球 Serve

依序觀察：

1. preparation_stability：準備姿勢是否穩定。
2. swing_completeness：揮拍動作是否完整。
3. body_coordination：身體與揮拍是否協調。
4. motion_smoothness：整體動作是否連續流暢。

填寫範例：

`preparation_stability=CLEAR; swing_completeness=CLEAR; body_coordination=PARTIAL; motion_smoothness=PARTIAL`

## 高遠球 Clear

依序觀察：

1. sideways_preparation：是否有側身準備。
2. weight_transfer：是否有明顯重心轉移。
3. non_racket_arm_balance：非持拍手是否協助平衡。
4. swing_smoothness：揮拍是否連續流暢。

填寫範例：

`sideways_preparation=CLEAR; weight_transfer=PARTIAL; non_racket_arm_balance=CLEAR; swing_smoothness=CLEAR`

## 人工與系統一致性

- AGREE：主要優缺點與整體高低一致。
- PARTIAL：部分維度一致，但有重要落差。
- DISAGREE：整體判斷或主要問題明顯相反。
- NOT_COMPARABLE：人工或系統無法完成可靠判斷。

## Issue Type

若出現落差，填寫最主要原因：

- THRESHOLD：門檻可能不合理。
- POSE_DETECTION：人體關節偵測問題。
- EVENT_DETECTION：動作事件切分問題。
- CAMERA_ANGLE：拍攝角度造成誤判。
- CAMERA_MOTION：攝影機晃動或位移，可能污染人體位移或穩定度 Feature。
- OCCLUSION：身體或球拍遮擋。
- MOTION_CLASSIFICATION：動作或方向分類錯誤。
- REPORT_MAPPING：後端結果與報告顯示不一致。
- UNKNOWN：暫時無法確認。
