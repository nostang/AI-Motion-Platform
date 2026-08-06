# v1.0.0-L3 — L3 Release Candidate

## Completed

- Frozen L3 pipeline: Pose → Motion → Feature → Calibration → Assessment → Coach → Summary → Report → API
- Added stable `result_summary` contract through `SummaryBuilder`
- Overall score uses four skill dimensions: Movement Completion, Recovery Speed, Motion Quality, and Body Stability
- Direction Coverage remains an independent review metric
- Added Motion Quality AR005 and Coach Rule CR007
- Added explainable feature feedback for shoulder, hip, and torso stability
- Added complete unittest discovery coverage for current L3 modules

## Validation

- Python compileall: PASS
- Unit and integration tests: 25/25 PASS
- End-to-end video execution must be verified locally because videos and runtime output are intentionally excluded from the release archive

## Freeze Boundary

Sport-specific technique rules such as split step, lead foot, and extra-step detection are not part of L3. They remain L4 work.
