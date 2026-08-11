# Engineer Mode V1

Engineer Mode is a table-first internal interface for tracing stored analysis
evidence. It is disabled by default and does not change the public Report.

## Entry

Open an existing report and select **工程模式**, or append `&engineer=1` to the
report URL.

Internal endpoint:

```text
GET /api/v1/internal/motion-assessments/{assessment_id}/engineer-debug
```

The route is intentionally excluded from the public OpenAPI schema.

## Evidence chain

The response joins, without rescoring:

- source-video container metadata;
- `human_annotation.json` when present;
- the stored motion assessment artifact;
- internal event or motion-window evidence;
- pose detection evidence;
- raw feature output;
- stored metric decisions and the matching calibration thresholds;
- the stored public-report summary and breakdown.

Missing evidence is returned explicitly as an `evidence_gap`; the interface
does not infer or invent unavailable values.

## UI structure

The default view is deliberately compact:

1. analysis summary table;
2. scoring-source table (`metric → feature → value → threshold → level → score`);
3. Footwork event table or Serve/Clear window table;
4. collapsed Raw JSON for engineering audit.

The Backend prepares the presentation rows. The browser formats and displays
them only; it does not calculate features, levels, sub-scores, or totals.
Footwork direction coverage is marked as diagnostic and excluded from the
overall score.

## Motion-specific coverage

- **Footwork:** event windows, per-event motion features, recovery, direction
  coverage, body stability, motion quality, calibration snapshot, and public
  report score composition.
- **Serve:** human analysis range, nested swing window, manual/automatic/
  effective side, raw serve features, metric decisions, and thresholds.
- **Clear:** human analysis range, clear event window, racket-hand estimate,
  raw clear features, metric decisions, and thresholds. Clear currently has no
  separate nested feature window; this is shown as an evidence gap.

## Contract boundary

No public response field or formal Web Integration Contract is changed.
Engineer Mode must remain an internal/debug surface.
