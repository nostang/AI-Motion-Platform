# AI Coach Contract V1

## 1. Purpose

AI Coach V1 consumes the existing Competency Profile and Competency Interpretation and produces a structured coaching recommendation JSON.

This layer does **not**:
- re-run motion analysis
- change Footwork / Serve / Clear scores
- create a cross-motion overall score
- declare an official badminton level

Its responsibility is to turn existing evidence into explainable coaching recommendations.

---

## 2. Input Contract

Required inputs:

```json
{
  "profile": {
    "profile_version": "competency-profile-v1.1",
    "profile_status": "COMPLETE",
    "motions": {
      "footwork": {},
      "serve": {},
      "clear": {}
    }
  },
  "interpretation": {
    "engine_version": "competency-engine-v1.0",
    "status": "READY",
    "strengths": [],
    "improvement_priorities": []
  }
}
```

The engine must use only evidence already present in these structures.

---

## 3. Output Contract

```json
{
  "schema_version": "1.0",
  "coach_version": "ai-coach-v1.0",
  "status": "READY",
  "player_id": "1",

  "strengths": [],

  "improvement_priorities": [],

  "training_recommendations": [],

  "suggested_playing_level": {
    "status": "INSUFFICIENT_EVIDENCE",
    "suggested_range": null,
    "confidence": null,
    "evidence_coverage": {
      "motion_assessment": true,
      "match_or_rally_evidence": false
    }
  },

  "reasoning": [],

  "limitations": []
}
```

---

## 4. Coaching Rules

### Strengths
Reuse `Competency Interpretation.strengths`.

### Improvement Priorities
Reuse `Competency Interpretation.improvement_priorities`.

`NEEDS_REVIEW` items remain higher priority than score-only weaknesses.

### Training Recommendations
V1 recommendations are rule-based and motion-specific.

Examples:
- `footwork` → footwork consistency / recovery / stability practice
- `serve` → serve consistency and smoothness practice
- `clear` → maintain high-clear technique and rhythm

The coach layer may explain existing findings but may not invent new motion measurements.

---

## 5. Suggested Playing Level

V1 does not automatically produce a badminton playing-level range from isolated motion assessments alone.

Reason:

Motion assessments answer:

> How well is this specific technique being performed?

Playing level requires broader game evidence such as:
- rally consistency
- shot selection
- court positioning
- transition between attack and defense
- decision making
- unforced errors
- doubles rotation / coordination
- performance under realistic rally speed

Therefore, when only the current Footwork / Serve / Clear assessments are available:

```json
{
  "status": "INSUFFICIENT_EVIDENCE",
  "suggested_range": null,
  "confidence": null
}
```

A future version may output a recommended range after `Game Competency` evidence is introduced.

This will remain an **AI Suggested Playing Level**, not an official ranking.

---

## 6. Explainability

Every recommendation must be traceable to source evidence.

Example:

```json
{
  "motion_type": "footwork",
  "recommendation": "Prioritize footwork stability practice.",
  "source": {
    "score": 77.0,
    "coach_status": "NEEDS_REVIEW"
  }
}
```

The engine must never return an unexplained level or training recommendation.

---

## 7. Confidence and Limitations

Future Suggested Playing Level confidence may consider:
- motion coverage
- assessment confidence
- number of observed skills
- rally / match evidence coverage
- video quality
- occlusion
- camera angle
- lighting
- frame loss / blur

V1 does not calculate this confidence yet.

Standard limitation text:

> AI coaching recommendations are generated from the available video evidence and may be affected by camera angle, lighting, occlusion, video quality, and incomplete skill coverage. Suggested playing level, when available in future versions, is intended as a training and game-selection reference rather than an official ranking.

---

## 8. Architecture

```text
Motion Analysis
      ↓
Report JSON
      ↓
PostgreSQL
      ↓
Competency Profile
      ↓
Competency Interpretation
      ↓
AI Coach V1
      ↓
Coach JSON
```

Every layer consumes structured data and produces structured JSON.
