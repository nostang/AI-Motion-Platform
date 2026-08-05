# AI Motion src v0.4.0

## 新增

- Motion Classification V1
- 八方向分類：FRONT、RIGHT_FRONT、RIGHT、RIGHT_BACK、BACK、LEFT_BACK、LEFT、LEFT_FRONT
- Center Reference → Reach Point 向量分類
- 正面拍攝左右鏡像處理
- 前後方向透視補償參數
- Debug Overlay 顯示 Direction 與 Direction Angle
- Terminal 輸出 Motion Classification 結果

## 保留

- Footwork Event V2
- Center Offset 平滑
- Direction Reversal
- Hysteresis
- READY Debounce
- Reach Event 回溯最遠 Frame

## 注意

目前方向分類是單鏡頭 2D L3 版本。前後方向可能受透視、身體蹲低與拍攝角度影響，需以實際八方向影片驗證後調整 DIRECTION_Y_SCALE。
