# Body Stability Robustness V2 — Simulation Only

This folder is deliberately isolated from the production AI Motion scoring path.

It does **not** modify:

- `src/assessment/body_stability.py`
- `src/config_data/footwork_calibration.json`
- production tests
- API contracts
- coach logic

## Run

```bash
python tools/body_stability_v2_simulation.py
```

## What it compares

Current V1 hard-boundary behavior versus one illustrative continuous-scoring
candidate using the same current thresholds and weights.

The candidate formula is **not approved calibration**. It exists only to
measure sensitivity using the real Original vs 720p Footwork values observed
during normalization testing.
