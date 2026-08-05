# CHANGELOG v0.9.0 — API Module

- Added FastAPI adapter under `src/api/`.
- Added the three API Contract v1.0 endpoints.
- Added file-backed task/status repository and background pipeline service.
- Added MP4/MOV, 100 MB, and 3–30 second validation.
- Added standard response envelope and contract error codes.
- Refactored `run_pose_demo()` to support headless API execution, per-task output directories, and structured return values.
- Added `api_main.py` and API repository tests.
- No Motion, Assessment, Coach, Report, Review, or Validator algorithm was changed.
