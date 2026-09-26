# Motion Feature Catalog

- **Status:** Current index
- **Owner:** AI Motion features
- **Last verified:** 2026-09-02

| Motion | Event source | Feature source | Assessment source |
| --- | --- | --- | --- |
| Footwork | `../../../src/event/footwork_event.py` | `../../../src/features/motion_features.py` | `../../../src/assessment/footwork_assessment.py` |
| Serve | `../../../src/event/serve_event.py` | `../../../src/features/serve_features.py` | `../../../src/assessment/serve_assessment.py` |
| Clear | `../../../src/event/clear_event.py` | `../../../src/features/clear_features.py` | `../../../src/assessment/clear_assessment.py` |

共同 measurement 命名與品質規則見
[Measurement Specification](../Core/Measurement_Specification.md)。新增 feature 必須
定義單位、缺值語意、可觀測前提與測試，不可只在 report 文案中出現。
