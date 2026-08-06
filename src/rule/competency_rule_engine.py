"""通用 Competency Rule Engine。

將既有 Assessment Result 依照可版本化規則整合為 Competency。
本模組不讀取 MediaPipe、不重新計算 Feature，也不修改原 Assessment。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class CompetencyRule:
    source_key: str
    weight: float
    required: bool = True


class CompetencyRuleEngine:
    """依照規則設定整合多個 Assessment 分數。"""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = dict(config)
        self.rules = self._load_rules(config)

    @staticmethod
    def _load_rules(
        config: Mapping[str, Any],
    ) -> tuple[CompetencyRule, ...]:
        raw_rules = config.get("components")
        if not isinstance(raw_rules, list) or not raw_rules:
            raise ValueError("Competency config 必須包含非空 components。")

        rules: list[CompetencyRule] = []
        total_weight = 0.0

        for item in raw_rules:
            if not isinstance(item, Mapping):
                raise ValueError("components 每一項必須是 object。")

            source_key = str(item.get("source_key", "")).strip()
            weight = float(item.get("weight", 0.0))
            required = bool(item.get("required", True))

            if not source_key:
                raise ValueError("component source_key 不可為空。")
            if weight <= 0:
                raise ValueError(
                    f"{source_key} 的 weight 必須大於 0。"
                )

            total_weight += weight
            rules.append(
                CompetencyRule(
                    source_key=source_key,
                    weight=weight,
                    required=required,
                )
            )

        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(
                f"components 權重總和必須為 1.0，目前為 {total_weight:.6f}。"
            )

        return tuple(rules)

    @staticmethod
    def _read_score(
        assessment: Mapping[str, Any],
        source_key: str,
    ) -> tuple[float | None, float | None, str | None]:
        result = assessment.get(source_key)

        if not isinstance(result, Mapping):
            return None, None, None

        score = result.get("score")
        max_score = result.get("max_score")
        status = result.get("status")

        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return None, None, str(status) if status is not None else None

        if (
            isinstance(max_score, bool)
            or not isinstance(max_score, (int, float))
            or float(max_score) <= 0
        ):
            return None, None, str(status) if status is not None else None

        return (
            float(score),
            float(max_score),
            str(status) if status is not None else None,
        )

    def evaluate(
        self,
        assessment: Mapping[str, Any],
    ) -> dict[str, Any]:
        components: list[dict[str, Any]] = []
        missing_required: list[str] = []
        weighted_score = 0.0

        for rule in self.rules:
            score, max_score, source_status = self._read_score(
                assessment,
                rule.source_key,
            )

            evaluated = (
                score is not None
                and max_score is not None
                and source_status == "EVALUATED"
            )

            if not evaluated:
                if rule.required:
                    missing_required.append(rule.source_key)

                components.append(
                    {
                        "source_key": rule.source_key,
                        "weight": rule.weight,
                        "required": rule.required,
                        "status": "NOT_EVALUATED",
                        "source_status": source_status,
                        "score": score,
                        "max_score": max_score,
                        "normalized_score": None,
                        "weighted_contribution": None,
                    }
                )
                continue

            normalized_score = max(
                0.0,
                min(100.0, score / max_score * 100.0),
            )
            contribution = normalized_score * rule.weight
            weighted_score += contribution

            components.append(
                {
                    "source_key": rule.source_key,
                    "weight": rule.weight,
                    "required": rule.required,
                    "status": "EVALUATED",
                    "source_status": source_status,
                    "score": score,
                    "max_score": max_score,
                    "normalized_score": round(normalized_score, 2),
                    "weighted_contribution": round(contribution, 2),
                }
            )

        if missing_required:
            return {
                "status": "NOT_EVALUATED",
                "competency_id": self.config["competency_id"],
                "competency_name": self.config["competency_name"],
                "competency_version": self.config["competency_version"],
                "rule_version": self.config["rule_version"],
                "overall_score": None,
                "level": None,
                "components": components,
                "missing_required_components": missing_required,
                "limitations": list(
                    self.config.get("limitations", [])
                ),
            }

        overall_score = round(weighted_score, 1)
        level = self._score_level(overall_score)

        return {
            "status": "EVALUATED",
            "competency_id": self.config["competency_id"],
            "competency_name": self.config["competency_name"],
            "competency_version": self.config["competency_version"],
            "rule_version": self.config["rule_version"],
            "overall_score": overall_score,
            "level": level,
            "components": components,
            "missing_required_components": [],
            "limitations": list(
                self.config.get("limitations", [])
            ),
        }

    def _score_level(self, score: float) -> str:
        thresholds = self.config.get("level_thresholds")
        if not isinstance(thresholds, Mapping):
            raise ValueError("Competency config 缺少 level_thresholds。")

        if score >= float(thresholds["EXCELLENT"]):
            return "EXCELLENT"
        if score >= float(thresholds["GOOD"]):
            return "GOOD"
        if score >= float(thresholds["FAIR"]):
            return "FAIR"
        return "POOR"
