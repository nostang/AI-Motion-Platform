# AI Motion Assessment Platform — L3 Freeze

Release candidate: `v1.0.0-L3`

## Frozen pipeline

`Pose → Motion → Feature → Calibration → Assessment → Coach → Summary → Report → API`

## Completed L3 assessment contract

- AR001 Movement Completion
- AR002 Recovery Speed
- AR003 Direction Coverage — independent review metric, excluded from the 100-point overall score
- AR004 Body Stability
- AR005 Motion Quality
- Feature-based Coach feedback and training suggestions
- Stable `result_summary.overall` contract

## Overall score contract

The 100-point overall score is generated only from four evaluated skill dimensions:

- Movement Completion
- Recovery Speed
- Motion Quality
- Body Stability

Direction Coverage remains an independent assessment metric because incomplete coverage may be caused by the performed motion, camera angle, or classification uncertainty.

## Confidence semantics

`result_summary.overall.confidence` reuses the Assessment `system_confidence`. The Summary layer does not create a new confidence model.

## Freeze rule

After this release, Feature, Calibration, Assessment, and Coach layers are frozen except for verified defects or calibration updates. Sport-specific technique rules such as split step, lead foot, and extra-step detection belong to L4.
