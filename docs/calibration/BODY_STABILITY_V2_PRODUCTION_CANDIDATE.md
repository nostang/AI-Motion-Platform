# Body Stability V2 — Production Candidate

Status: CANDIDATE / NOT PRODUCTION
Scope: Footwork AR004 Body Stability
Current production implementation: Body Stability V1
Candidate purpose: Improve scoring robustness while preserving discrimination.

---

## 1. Background

Body Stability V1 evaluates:

- MF001 — Shoulder Tilt
- MF002 — Hip Tilt
- MF003 — Torso Lean

Current production flow:

Measurement
→ calibrated hard Feature Level
→ level points (4 / 3 / 2 / 1)
→ weighted level points
→ hard overall level
→ fixed score (25 / 22 / 18 / 12)

Current feature weights:

- MF001 Shoulder Tilt: 0.35
- MF002 Hip Tilt: 0.35
- MF003 Torso Lean: 0.30

Existing calibration thresholds remain PROVISIONAL.

---

## 2. Problem Observed

Testing showed that Body Stability V1 can amplify small measurement differences near hard calibration boundaries.

Example from the same Footwork source motion:

Original:

- MF001: 15.5245 → POOR
- MF002: 10.5511 → POOR
- MF003: 3.3624 → EXCELLENT
- Body Stability: 12 / POOR

720p preserve-timing version:

- MF001: 13.3181 → POOR
- MF002: 9.4668 → FAIR
- MF003: 3.2920 → EXCELLENT
- Body Stability: 18 / FAIR

A relatively small change in MF002 crossed the FAIR boundary and produced a 6-point Body Stability change.

This behavior is referred to in this document as:

**Hard-boundary amplification.**

This observation does not establish that the existing thresholds are biomechanically incorrect.

---

## 3. V2 Design Goal

Body Stability V2 should:

1. Reduce score discontinuities around calibration boundaries.
2. Preserve continuous measurement information.
3. Remain monotonic: worse measurements must not produce better scores.
4. Remain discriminative between different measurement profiles.
5. Preserve the existing three-feature interpretation.
6. Avoid changing calibration thresholds without separate evidence.
7. Avoid changing the Public API Contract during candidate validation.

---

## 4. Candidate Scoring Flow

Candidate V2 flow:

Measurement
→ Continuous Feature Points
→ Weighted Continuous Points
→ Continuous Body Stability Score
→ Display Level

Key design principle:

**Score is continuous. Level is an interpretation of the score and does not determine the score.**

This differs from V1, where hard Feature Levels directly determine the final score.

---

## 5. Continuous Feature Mapping Candidate

The current simulation uses the existing V1 threshold locations.

For lower-is-better features:

- value <= EXCELLENT threshold:
  - 4.0 points

- EXCELLENT → GOOD:
  - linear interpolation from 4.0 → 3.0

- GOOD → FAIR:
  - linear interpolation from 3.0 → 2.0

- above FAIR:
  - linear interpolation from 2.0 → 1.0 across one additional `(FAIR - GOOD)` span
  - floor at 1.0

This mapping is currently a candidate only.

It does not redefine the existing calibration thresholds.

---

## 6. Feature Weights

Candidate V2 currently preserves the V1 weights:

| Feature | Weight |
|---|---:|
| MF001 Shoulder Tilt | 0.35 |
| MF002 Hip Tilt | 0.35 |
| MF003 Torso Lean | 0.30 |

No evidence collected during V2.1–V2.3 is sufficient to justify changing these weights.

Therefore the weights remain unchanged for the production candidate.

---

## 7. Continuous 25-Point Mapping

Weighted feature points remain in the range 1.0–4.0.

The current candidate maps these points through the existing V1 score anchors:

- 1.0 → 12
- 2.0 → 18
- 3.0 → 22
- 4.0 → 25

Piecewise-linear interpolation is used between anchors.

Example:

A weighted value between 2.0 and 3.0 produces a continuous score between 18 and 22.

Candidate internal scores may therefore contain decimals.

Final presentation / rounding policy is not yet frozen.

---

## 8. Validation Results

### V2.1 — Mathematical Robustness

Result: PASS

Validated:

- monotonicity
- boundary robustness
- discrimination

The continuous candidate substantially reduced artificial score jumps around hard V1 boundaries.

This validation establishes mathematical behavior only.

---

### V2.2 — Same-Motion / Format Robustness

Result: PASS

FW001 comparison:

V1:

- Original Body Stability: 12
- 720p preserve timing: 18
- Range: 6 points

V2 shadow:

- Original: 19.385
- 720p preserve timing: 20.279
- Range: 0.894 points

Additional 720p30 shadow result:

- 19.656

Observed V2 shadow range:

0.894 points

The candidate substantially reduced sensitivity to video-format-induced measurement variation in this sample.

---

### V2.3 — Cross-Sample Discrimination

Result: PASS — preliminary

Three real Footwork measurement profiles were compared.

| Sample | V1 | V2 Shadow |
|---|---:|---:|
| FW001 | 18 | 20.279 |
| Existing Sample | 12 | 19.756 |
| FW002 | 12 | 18.404 |

Important comparison:

Existing Sample vs FW002:

- V1 difference: 0
- V2 difference: 1.352

V1 collapsed both profiles to the same fixed score.

V2 retained a measurable distinction between them.

This provides preliminary evidence that reducing boundary sensitivity does not necessarily eliminate cross-sample discrimination.

---

## 9. Video Normalization Observation

Testing also provided evidence supporting a preprocessing candidate:

- H.264
- approximately 720p
- preserve source timing
- do not force 30 FPS

Observed benefits included substantial file-size reduction and faster Cloud Run analysis.

For FW002:

- original analyzer time: 77.528 s
- normalized analyzer time: 48.679 s
- both analyses processed 943 frames

This preprocessing observation is related to robustness testing but is not itself part of the Body Stability scoring formula.

A separate capture / preprocessing specification should govern production normalization behavior.

---

## 10. Production Compatibility

During candidate validation:

- Body Stability V1 remains production.
- `src/assessment/body_stability.py` remains authoritative.
- Existing calibration thresholds remain unchanged.
- Existing feature weights remain unchanged.
- Coach logic remains unchanged.
- Report behavior remains unchanged.
- Public API Contract remains unchanged.
- Web Integration Contract remains unchanged.

V2 calculations are shadow / simulation only.

---

## 11. Current Candidate Decision

The following design direction is accepted for continued evaluation:

**Measurement → Continuous Feature Points → Weighted Continuous Score → Display Level**

The following are NOT yet approved:

- replacing V1 production scoring
- changing calibration thresholds
- changing feature weights
- changing coach rules
- changing Public API fields or semantics
- claiming biomechanical validity
- claiming coach-validated calibration

---

## 12. Remaining Questions Before Production

Before V2 can replace V1, the following must be decided or validated:

1. Final continuous mapping formula.
2. Final rounding / display policy.
3. Final Display Level boundaries.
4. Whether coach rules consume numeric score, Display Level, or both.
5. Behavior near extreme POOR measurements.
6. Regression behavior across a larger sample set.
7. Coach / expert validation of Body Stability interpretation.
8. Whether current provisional thresholds remain appropriate.

---

## 13. Current Verdict

V2.1 Mathematical Robustness: PASS
V2.2 Same-Motion Format Robustness: PASS
V2.3 Cross-Sample Discrimination: PASS (preliminary)

Overall engineering verdict:

**BODY STABILITY V2 CONTINUOUS-SCORING DIRECTION: CANDIDATE PASS**

This verdict means the design is sufficiently promising to proceed toward a production candidate.

It does NOT mean:

- production approval
- calibration completion
- biomechanical validation
- coach validation

Body Stability V1 remains the production scoring implementation until a separate implementation and regression phase is explicitly approved.

---

## 14. Report / Coach Compatibility Finding

Production compatibility review identified an important Report V1 behavior.

`CR006` forwards Body Stability evidence including:

- result
- level
- score
- weighted_level_points
- feature_levels

`ReportBuilder._rule_numeric_score()` accepts numeric Body Stability scores as
`float` and forwards them without rounding.

Therefore a future continuous Body Stability score such as `19.4` is compatible
with the current numeric report transport.

However, `ReportBuilder._dimension_level()` currently preserves only these
Assessment levels:

- EXCELLENT
- GOOD
- POOR

`FAIR` is not preserved.

If Assessment V2 produced:

- score: 19.4
- level: FAIR

the current Report Builder would ignore FAIR and recompute the UI dimension
level from score ratio.

For example:

19.4 / 25 = 0.776

Under the current three-level UI mapping this becomes:

GOOD

This would create a semantic mismatch:

Assessment level: FAIR
Report level: GOOD

Therefore Body Stability V2 must not enter production until Assessment and
Report level semantics are explicitly aligned.

Candidate requirement:

**One authoritative Body Stability display-level interpretation must be used
across Assessment, Coach, Report, Radar, and user-facing result views.**

---

## 15. Candidate Production Semantics

The current recommended V2 semantics are:

### Numeric Score

- Body Stability score becomes continuous.
- Internal score may contain decimals.
- Existing numeric field names remain unchanged.
- Final rounding / presentation policy remains to be frozen.

Example:

`19.4 / 25`

### Feature Levels

MF001 / MF002 / MF003 feature levels remain available for explanation and coach
feedback.

They no longer determine the Body Stability numeric score.

### Body Stability Level

Body Stability level is derived from the final continuous Body Stability score
or weighted continuous points.

It is an interpretation layer, not a scoring input.

### Result

Candidate behavior:

- EXCELLENT → PASS
- GOOD → PASS
- FAIR → NEEDS_REVIEW
- POOR → NEEDS_REVIEW

This preserves the current intent that lower-confidence Body Stability outcomes
remain reviewable.

### Report Compatibility

Before production adoption, Report Builder must support the authoritative V2
Body Stability level semantics.

The current behavior that ignores `FAIR` is not compatible with a four-level V2
Assessment contract.

---

## 16. Contract Impact Classification

Body Stability V2 is not merely an internal refactor.

Although existing JSON field names can remain unchanged, the semantic domain of
`body_stability.score` changes from a fixed discrete set:

12 / 18 / 22 / 25

to a continuous numeric score in the 25-point scale.

Therefore V2 should be treated as a:

**Scoring Semantic Change**

not as a transport-level API shape change.

Public endpoint paths and JSON field names do not need to change solely because
of V2, but downstream consumers must be regression-tested against the new score
semantics before production release.
