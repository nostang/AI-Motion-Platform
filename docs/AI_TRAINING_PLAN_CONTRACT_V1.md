# AI Training Planner Contract V1

## 1. Purpose

AI Training Planner V1 converts the existing AI Coach JSON into a structured,
explainable training plan.

This layer does **not**:
- re-run motion analysis
- change motion scores
- change Competency results
- generate new playing-level conclusions
- use an LLM to invent exercises

Its responsibility is only:

```text
AI Coach JSON
    ↓
Rule-based training plan
    ↓
Training Plan JSON
```

## 2. Input Contract

Required input:

```json
{
  "coach_version": "ai-coach-v1.0",
  "status": "READY",
  "player_id": "1",
  "strengths": [],
  "improvement_priorities": [],
  "training_recommendations": []
}
```

## 3. Output Contract

```json
{
  "schema_version": "1.0",
  "plan_version": "training-plan-v1.0",
  "rule_version": "training-plan-rule-v1.0",
  "status": "READY",
  "player_id": "1",
  "estimated_training_sessions": 6,
  "training_plan": [],
  "maintenance_plan": [],
  "reassessment": {
    "recommended": true,
    "after_priority_sessions": 6,
    "recommended_motion": "footwork"
  },
  "limitations": []
}
```

## 4. Planning Rules

Default session allocation:

```text
HIGH     → 3 sessions
MEDIUM   → 2 sessions
LOW      → 1 session
MAINTAIN → 1 maintenance session
```

## 5. Reassessment Rule

The first/highest-priority motion becomes the recommended reassessment motion.
Maintenance sessions do not delay reassessment.

## 6. Explainability

Every plan item must preserve source evidence whenever available.

## 7. Limitations

V1 is a practice-planning reference only. Session counts are provisional and
have not been coach-calibrated. The planner does not know actual session
duration, intensity, fatigue, injury status, or whether the user completed a
session.

## 8. Architecture Rule

```text
Contract
↓
Rules
↓
Engine
↓
API
↓
Test
```

Input and output remain structured JSON.
