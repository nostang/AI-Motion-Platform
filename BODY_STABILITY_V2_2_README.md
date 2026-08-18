# Body Stability V2.2 — Shadow Comparison

Reads existing Footwork report JSON files and compares production V1 Body
Stability against the illustrative continuous V2 shadow candidate.

No production file is changed.

## Default run

```bash
python tools/body_stability_v22_shadow.py
```

Expected input files:

- `/tmp/footwork_original.json`
- `/tmp/footwork_normalized.json`
- `/tmp/footwork_720p_originalfps.json`

It also writes:

`/tmp/body_stability_v22_shadow.csv`

## Important

A PASS only means the V2 candidate reduced normalization sensitivity for this
shadow comparison set. It is not approval for production replacement.
