"""正手發球教學動作 Coach：只解釋 Assessment，不重新計分。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LABELS = {
    "preparation_stability": "準備姿勢穩定度",
    "swing_completeness": "揮拍動作完整性",
    "body_coordination": "身體協調與軀幹變化",
    "motion_smoothness": "動作流暢度",
}


def build_serve_coach(assessment: dict[str, Any]) -> dict[str, Any]:
    metrics = assessment.get("metrics") or {}
    feedback = []
    for key, item in metrics.items():
        level = item.get("level")
        if level in {"EXCELLENT", "GOOD"}:
            message = f"{_LABELS.get(key, key)}表現穩定，可維持目前節奏。"
        elif level == "FAIR":
            message = f"{_LABELS.get(key, key)}尚可，建議放慢動作確認完整路徑。"
        else:
            message = f"{_LABELS.get(key, key)}需要優先改善，建議分解練習後再連續完成。"
        feedback.append({"metric": key, "level": level, "message": message})

    if assessment.get("evaluation_status") != "EVALUATED":
        overall_status = "NOT_EVALUATED"
        overall_message = "有效 Pose 樣本不足，暫不提供發球評分。"
    else:
        score = assessment.get("overall_score") or 0
        overall_status = "PASS" if score >= 70 else "NEEDS_REVIEW"
        overall_message = (
            "整體正手發球教學動作完整，可維持目前節奏並持續練習。"
            if score >= 70
            else "目前正手發球動作仍有改善空間，建議優先練習最低分項目。"
        )

    return {
        "schema_version": "0.1",
        "coach_engine_version": "serve-coach-v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assessment_id": assessment["assessment_id"],
        "assessment_type": "serve",
        "serve_type": assessment.get("serve_type", "forehand"),
        "test_completed": assessment.get("test_completed", False),
        "overall_status": overall_status,
        "overall_message": overall_message,
        "feedback": feedback,
        "gemini_input_ready": True,
        "limitations": list(assessment.get("limitations", [])),
    }


def save_serve_coach(result: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
