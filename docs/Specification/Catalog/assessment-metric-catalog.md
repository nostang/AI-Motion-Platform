# Assessment Metric Catalog

- **Status:** Current index
- **Owner:** AI Motion assessment
- **Last verified:** 2026-09-02

本檔不另列可能過期的分數與 threshold，而是記錄 metric 的權威來源：

| Motion | Calibration／rubric | Assessment implementation |
| --- | --- | --- |
| Footwork | `../../../src/config_data/footwork_calibration.json` | `../../../src/assessment/footwork_assessment.py` |
| Serve | `../../../src/config_data/serve_calibration.json` | `../../../src/assessment/serve_assessment.py` |
| Clear | `../../../src/config_data/clear_calibration.json`、`clear_rubric.json` | `../../../src/assessment/clear_assessment.py` |

Metric 的共同語意、weight、overall score 與 confidence 原則見
[Assessment Specification](../Core/Assessment_Specification.md)。變更 metric 時必須
同步校正檔、assessment code、API／report contract 與 regression tests。
