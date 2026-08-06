# CHANGELOG v1.3.0 — Motion Feature Library V1

## Added

- MF001 Shoulder Tilt
- MF002 Hip Tilt
- MF003 Torso Lean
- Event-level feature statistics and pose-quality metadata
- Assessment schema version 1.3

## Design Decisions

- Feature extraction is separated from scoring.
- Motion Features are descriptive 2D values and do not directly represent body stability.
- MF001 and MF002 require angle normalization before use in Body Stability assessment.
