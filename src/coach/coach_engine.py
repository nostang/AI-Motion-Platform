"""Coach Module V1.2。

將 Footwork Assessment 的客觀結果轉換為教練可理解、可追溯的
Coach Evaluation JSON。本模組不產生技術分數，也不重新分析影片。
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from src.coach.coach_rules import COACH_RULES


class CoachEngine:
    """執行 Coach Rule Library 並建立 Coach Evaluation JSON。"""

    def __init__(self, version: str = "1.2") -> None:
        self.version = version

    @staticmethod
    def _validate_assessment(assessment: dict[str, Any]) -> None:
        """檢查 Coach Module 所需的最小 Assessment 契約。"""

        if not isinstance(assessment, dict):
            raise TypeError("assessment 必須是 dict。")

        required_fields = (
            "assessment_id",
            "assessment_type",
            "analysis_status",
            "events",
        )
        missing_fields = [
            field for field in required_fields if field not in assessment
        ]
        if missing_fields:
            raise ValueError(
                "Assessment 缺少必要欄位："
                + ", ".join(missing_fields)
            )

        if assessment.get("assessment_type") != "footwork":
            raise ValueError(
                "Coach Module V1 只支援 assessment_type='footwork'。"
            )

        if not isinstance(assessment.get("events"), list):
            raise ValueError("Assessment events 必須是 list。")

    def evaluate(self, assessment: dict[str, Any]) -> dict[str, Any]:
        """依 Footwork Assessment JSON 產生 Coach Evaluation JSON。"""

        self._validate_assessment(assessment)

        rules = [rule(assessment) for rule in COACH_RULES]
        results = [rule["result"] for rule in rules]

        if "FAIL" in results:
            overall_status = "FAIL"
        elif "NEEDS_REVIEW" in results:
            overall_status = "NEEDS_REVIEW"
        elif results and all(result == "PASS" for result in results):
            overall_status = "PASS"
        else:
            overall_status = "NOT_EVALUATED"

        return {
            "schema_version": "1.0",
            "coach_engine_version": self.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "assessment_id": assessment.get("assessment_id"),
            "assessment_type": assessment.get("assessment_type"),
            "engine_version": assessment.get("engine_version"),
            "config_version": assessment.get("config_version"),
            "assessment_analysis_status": assessment.get("analysis_status"),
            "test_completed": bool(
                assessment.get("test_completed", False)
            ),
            "rules": rules,
            "checklist_summary": {
                "pass_count": results.count("PASS"),
                "fail_count": results.count("FAIL"),
                "needs_review_count": results.count("NEEDS_REVIEW"),
                "not_evaluated_count": results.count("NOT_EVALUATED"),
            },
            "overall_status": overall_status,
            "technique_score": None,
            "timing_used_for_score": True,
            "not_evaluated": [
                "lead_foot",
                "dominant_hand_rule",
                "extra_steps",
                "split_step",
                "body_stability_score",
                "coach_similarity_score",
            ],
            "expert_review_recommended": (
                overall_status == "NEEDS_REVIEW"
            ),
            "gemini_input_ready": True,
        }

    @staticmethod
    def save(result: dict[str, Any], output_path: Path) -> None:
        """將 Coach Evaluation JSON 儲存為 UTF-8。"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
