# AI Motion Capture Standard V1

## Scope

This is Reference Web capture guidance and client-side quality assistance. It does not change Backend API validation, request fields, or public response schemas.

## Common capture guidance

- Record at normal 1.0x speed.
- Use one fixed camera view without edits or replay.
- Keep the full body and racket visible.
- Use sufficient, even lighting and avoid severe backlight.
- Avoid other people blocking the subject.
- Fix the phone or camera in place when practical.
- No mandatory FPS or resolution threshold is introduced in V1.

## Motion guides

- Footwork: semi-transparent half-court overlay for visual alignment only. It does not detect court lines.
- Serve: a fixed framing guide with a three-frame looping pose sequence (ready, swing, finish). A badminton court is not required.
- Clear: a fixed framing guide with a three-frame looping pose sequence (ready, overhead preparation, high contact), with additional overhead room for the racket arm. A badminton court is not required.

## Live quality checks

The camera UI checks:

- Full body in frame
- Appropriate subject distance
- Sufficient light

The state changes only after consecutive samples to reduce flicker. A PASS means the current capture conditions are suitable for analysis; it does not mean the badminton action is technically correct.

If pose detection cannot load, pose-based checks become unavailable without blocking recording. Existing camera, upload, trim, and analysis flows remain available.

## Contract impact

- Backend API / OpenAPI: unchanged
- Public response schema: unchanged
- Reference Web behavior: changed
- Web Integration Pack: add this guidance and mention it in the changelog
