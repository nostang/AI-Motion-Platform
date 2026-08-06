# AI Motion Platform Architecture

## Current Architecture

```text
Browser Frontend
(HTML / CSS / JavaScript)
        │
        │ HTTP / JSON
        ▼
FastAPI REST API
        │
        ▼
Video + Pose Detection
(MediaPipe Pose)
        │
        ▼
Measurement / Motion Feature Library
        │
        ▼
Footwork Event Engine
        │
        ▼
Assessment Metrics
(AR001 / AR002 / AR003)
        │
        ▼
Coach Rules
(CR001–CR005)
        │
        ▼
Report Builder + Review Package
        │
        ▼
Pipeline Validator
        │
        ▼
JSON Report / Interactive Report
```

## Architecture Diagram

![AI Motion Platform Architecture](architecture.png)

## Responsibility Boundary

| Layer | Responsibility | Must Not Do |
|---|---|---|
| Pose Detection | Detect body landmarks | Produce coaching scores |
| Measurement / Feature | Extract descriptive values | Decide PASS or FAIL |
| Event Engine | Segment MOVE / RECOVER events | Generate training advice |
| Assessment | Convert evidence into objective metrics | Pretend to be a human coach |
| Coach | Explain results and review status | Recalculate pose or events |
| Report | Assemble a stable output contract | Invent missing scores |
| API / Frontend | Expose and display platform capability | Reimplement AI rules |

## Extension Model

Future assessment types such as `serve` and `clear` may reuse the API, task repository, validator, report shell, and frontend shell. Each assessment type must provide its own event definition, feature selection, assessment rules, coach rules, and calibration version.
