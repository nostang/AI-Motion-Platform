# Motion Design Guide

- **Status:** Current index
- **Owner:** AI Motion
- **Last verified:** 2026-09-02

設計或修改一個 motion type 時，依序確認：

1. Teaching goal 與不可評估情境。
2. Pose／影格品質與輸入 validator。
3. 可觀測事件與事件順序。
4. Feature 名稱、單位、缺值與 confidence。
5. Calibration、metric、weight 與 overall score。
6. Coach rule、training plan 與限制文案。
7. API／report backward compatibility。
8. Unit、fixture、pipeline、Web contract 與真實影片驗證。

規格入口見 [Specification index](README.md)，metric 與 feature 來源見
[Catalog](Catalog/README.md)。新 motion 未完成上述鏈路前不得加入公開 supported
type，也不得只靠前端文案宣稱已支援。
