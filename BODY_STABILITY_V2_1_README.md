# Body Stability Robustness V2.1 — Sensitivity Sweep

Simulation only. No production scoring code is changed.

## Run

```bash
python tools/body_stability_v2_simulation.py
```

## Automated checks

- Monotonicity
- Boundary robustness around current hard thresholds
- Extreme discrimination
- Real Original vs 720p case retained for comparison

A `PASS` only means the illustrative continuous candidate behaves sensibly in
these mathematical checks. It is **not** approval to replace production V1.
