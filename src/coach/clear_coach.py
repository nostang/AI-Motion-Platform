"""高遠球教學動作 Coach：只解釋 Assessment，不重新計分。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LABELS = {
    "sideways_preparation": "側身準備",
    "weight_transfer": "重心轉移",
    "non_racket_arm_balance": "非持拍手平衡",
    "swing_smoothness": "揮拍流暢度",
}


def build_clear_coach(assessment: dict[str, Any]) -> dict[str, Any]:
    metrics = assessment.get("metrics") or {}
    feedback = []

    for key, item in metrics.items():
        level = item.get("level")

        if level in {"EXCELLENT", "GOOD"}:
            message = (
                f"{_LABELS.get(key, key)}表現良好，可維持目前動作節奏。"
            )
        elif level == "FAIR":
            message = (
                f"{_LABELS.get(key, key)}尚可，建議放慢速度確認完整動作。"
            )
        else:
            message = (
                f"{_LABELS.get(key, key)}需要優先改善，建議分解練習後再進行完整揮拍。"
            )

        feedback.append(
            {
                "metric": key,
                "level": level,
                "message": message,
            }
        )

    if assessment.get("evaluation_status") != "EVALUATED":
        overall_status = "NOT_EVALUATED"
        overall_message = "有效 Pose 樣本不足，暫不提供高遠球評估。"
    else:
        score = assessment.get("overall_score") or 0

        overall_status = (
            "PASS"
            if score >= 70
            else "NEEDS_REVIEW"
        )

        overall_message = (
            "整體高遠球教學動作良好，可維持目前節奏持續練習。"
            if score >= 70
            else "目前高遠球動作仍有改善空間，建議優先改善最低分項目。"
        )

    return {
        "schema_version": "0.1",
        "coach_engine_version": "clear-coach-v0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assessment_id": assessment["assessment_id"],
        "assessment_type": "clear",
        "clear_type": assessment.get("clear_type", "high_clear"),
        "test_completed": assessment.get(
            "test_completed",
            False,
        ),
        "overall_status": overall_status,
        "overall_message": overall_message,
        "feedback": feedback,
        "gemini_input_ready": True,
        "limitations": list(
            assessment.get("limitations", [])
        ),
    }


def save_clear_coach(
    result: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )