# CHANGELOG v1.1.0 — Recovery Speed Assessment

## Added

- AR002 Recovery Speed
- `recovery-speed-v1` calibration contract
- CR005 Recovery Speed coach rule
- Recovery statistics: average, median, fastest, slowest, valid event count
- Partial scoring fields: `evaluated_score`, `evaluated_max_score`, `score_coverage`

## Design Decisions

- Calibration thresholds are provisional and not presented as validated coaching standards.
- `overall_score` remains `null` while required skill dimensions are not evaluated.
- Recovery Speed describes the current video's return timing, not complete footwork technique.
