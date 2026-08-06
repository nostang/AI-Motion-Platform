# CHANGELOG v1.2.0 — Direction Coverage Assessment

## Added

- AR003 Direction Coverage
- `direction-coverage-v1` contract
- Independent `assessment_metrics.direction_coverage` report output
- Direction Coverage added to radar chart data

## Design Decisions

- Direction Coverage is a test coverage metric, not a full technique score.
- Missing directions produce `NEEDS_REVIEW`, not an automatic user failure.
- Camera angle and classification error remain explicit limitations.
