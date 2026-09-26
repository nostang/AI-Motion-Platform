# Documentation Migration Notes

## Structural Changes

- Merged `Specification/` and `specifications/` into one official `Specification/` folder.
- Added `Specification/Core/`, `Specification/Catalog/`, and `Specification/Archive/`.
- Moved API documents into `docs/API/`.
- Moved the architecture diagram next to `architecture.md`.
- Renamed demo images to lowercase kebab-case.
- Added `docs/README.md`, `Specification/README.md`, and `Design/CHANGELOG.md` indexes.
- Removed `.DS_Store`, `__MACOSX`, and AppleDouble metadata.

## Content Corrections

- Updated Coach Engine specification to include CR005 Recovery Speed.
- Updated Report specification to reflect partial scores, `null` semantics, Direction Coverage, and current radar dimensions.
- Updated API Contract to distinguish implemented local MVP behavior from future Authentication and deployment work.
- Updated Architecture documentation to include Feature, Assessment, Coach, Report, Validator, API, and Frontend layers.

## Replacement Instruction

Replace the existing project `docs/` folder with the organized `docs/` folder in this package after keeping a backup of the old folder.
