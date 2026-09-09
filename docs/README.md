# AI Motion Platform documentation

This directory is the canonical home for platform contracts, implementation
guides, release notes, and calibration evidence.

## Start here

- [Platform contract](PLATFORM_CONTRACT.md)
- [API contract v2](API_CONTRACT_V2.md)
- [Web integration guide](web_integration/README.md)
- [Motion specification index](Specification/README.md)
- [v1.3.0-L3 release notes](Release/v1.3.0-L3.md)

## Product and API contracts

- [AI Coach contract](AI_COACH_CONTRACT_V1.md)
- [AI training plan contract](AI_TRAINING_PLAN_CONTRACT_V1.md)
- [Camera recording contract](CAMERA_RECORDING_CONTRACT_V1.md)
- [Progress contract](PROGRESS_CONTRACT_V1.md)
- [Web API contract](WEB_API_CONTRACT_V1.md)
- [Web page contract](WEB_PAGE_CONTRACT_V1.md)
- [Engineer mode](ENGINEER_MODE_V1.md)
- [Explainable pose retention](EXPLAINABLE_POSE_V1_RETENTION.md)

## Motion specifications

The [`Specification/`](Specification/README.md) directory contains the core
measurement, event, assessment, coach, report, and validation specifications;
motion-specific teaching guides; and the versioned feature, metric, and rule
catalogs.

## Web integration

The [`web_integration/`](web_integration/README.md) directory contains the API
endpoint index, OpenAPI description, frontend integration guide, capture
standard, implementation checklist, and sample payloads.

## Calibration and experiments

The [`calibration/`](calibration/) directory contains calibration contracts,
review rubrics, validation matrices, retained system results, and isolated
experiments. Body Stability V2 exploratory notes are grouped under
[`calibration/experiments/body-stability-v2/`](calibration/experiments/body-stability-v2/README.md).

## Releases and archive

- [`Release/`](Release/) contains versioned release and freeze notes.
- [`archive/`](archive/) retains historical migration notes for reference; it
  is not current setup guidance.

Generated runtime output belongs in the repository-root `output/` directory and
is intentionally excluded from version control.
