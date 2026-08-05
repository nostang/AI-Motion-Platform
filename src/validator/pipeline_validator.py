"""驗證 AI Motion Pipeline 各輸出 JSON 與跨模組契約。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from src.validator.validation_rules import (
    ASSESSMENT_EVENT_REQUIRED_FIELDS,
    ASSESSMENT_REQUIRED_FIELDS,
    COACH_REQUIRED_FIELDS,
    COACH_RULE_REQUIRED_FIELDS,
    REPORT_REQUIRED_FIELDS,
    REVIEW_EVENT_REQUIRED_FIELDS,
    REVIEW_REQUIRED_FIELDS,
    SUPPORTED_ASSESSMENT_TYPE,
    VALID_COACH_STATUSES,
    VALID_REVIEW_STATUSES,
    VALID_RULE_RESULTS,
    expected_type_name,
    is_instance_of_expected,
    unique_non_empty_strings,
)


VALIDATOR_VERSION = "1.0"


class PipelineValidationError(RuntimeError):
    """Pipeline Contract 驗證失敗。"""

    def __init__(self, report: Mapping[str, Any]) -> None:
        self.report = dict(report)
        errors = self.report.get("summary", {}).get("error_count", 0)
        super().__init__(f"Pipeline validation failed with {errors} error(s).")


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    artifact: str
    field: Optional[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "artifact": self.artifact,
            "field": self.field,
            "message": self.message,
        }


class PipelineValidator:
    """Validate generated artifacts without recalculating motion results."""

    def __init__(self, version: str = VALIDATOR_VERSION) -> None:
        self.version = version

    def validate(
        self,
        assessment: Mapping[str, Any],
        coach_evaluation: Mapping[str, Any],
        analysis_report: Mapping[str, Any],
        review_package: Mapping[str, Any],
        *,
        artifact_paths: Optional[Mapping[str, Path]] = None,
        raise_on_error: bool = False,
    ) -> dict[str, Any]:
        issues: list[ValidationIssue] = []

        artifacts = {
            "assessment": assessment,
            "coach_evaluation": coach_evaluation,
            "analysis_report": analysis_report,
            "review_package": review_package,
        }

        if artifact_paths is not None:
            self._validate_artifact_paths(artifact_paths, issues)

        self._validate_required_fields(
            "assessment", assessment, ASSESSMENT_REQUIRED_FIELDS, issues
        )
        self._validate_required_fields(
            "coach_evaluation", coach_evaluation, COACH_REQUIRED_FIELDS, issues
        )
        self._validate_required_fields(
            "analysis_report", analysis_report, REPORT_REQUIRED_FIELDS, issues
        )
        self._validate_required_fields(
            "review_package", review_package, REVIEW_REQUIRED_FIELDS, issues
        )

        self._validate_assessment(assessment, issues)
        self._validate_coach(coach_evaluation, issues)
        self._validate_report(analysis_report, issues)
        self._validate_review(review_package, issues)
        self._validate_cross_contracts(artifacts, issues)

        report = self._build_report(artifacts, artifact_paths, issues)
        if raise_on_error and report["summary"]["error_count"] > 0:
            raise PipelineValidationError(report)
        return report

    def validate_files(
        self,
        *,
        assessment_path: Path,
        coach_evaluation_path: Path,
        analysis_report_path: Path,
        review_package_path: Path,
        raise_on_error: bool = False,
    ) -> dict[str, Any]:
        paths = {
            "assessment": Path(assessment_path),
            "coach_evaluation": Path(coach_evaluation_path),
            "analysis_report": Path(analysis_report_path),
            "review_package": Path(review_package_path),
        }
        artifacts = {
            name: self._load_json(path, name)
            for name, path in paths.items()
        }
        return self.validate(
            artifacts["assessment"],
            artifacts["coach_evaluation"],
            artifacts["analysis_report"],
            artifacts["review_package"],
            artifact_paths=paths,
            raise_on_error=raise_on_error,
        )

    def save(self, report: Mapping[str, Any], output_path: Path) -> None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _load_json(path: Path, artifact: str) -> Mapping[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"{artifact} JSON 不存在：{path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{artifact} 不是有效 JSON：{path}") from exc
        if not isinstance(data, dict):
            raise TypeError(f"{artifact} JSON 根節點必須是 object。")
        return data

    @staticmethod
    def _validate_artifact_paths(
        artifact_paths: Mapping[str, Path],
        issues: list[ValidationIssue],
    ) -> None:
        for artifact, path in artifact_paths.items():
            if not Path(path).exists():
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "PV001",
                        artifact,
                        None,
                        f"輸出檔案不存在：{path}",
                    )
                )

    @staticmethod
    def _validate_required_fields(
        artifact: str,
        payload: Mapping[str, Any],
        required: Mapping[str, type | tuple[type, ...]],
        issues: list[ValidationIssue],
    ) -> None:
        if not isinstance(payload, Mapping):
            issues.append(
                ValidationIssue(
                    "ERROR", "PV002", artifact, None, "根節點必須是 object。"
                )
            )
            return

        for field, expected in required.items():
            if field not in payload:
                issues.append(
                    ValidationIssue(
                        "ERROR", "PV003", artifact, field, "缺少必要欄位。"
                    )
                )
                continue
            if not is_instance_of_expected(payload[field], expected):
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "PV004",
                        artifact,
                        field,
                        "欄位型別錯誤；預期 "
                        f"{expected_type_name(expected)}，實際 "
                        f"{type(payload[field]).__name__}。",
                    )
                )

    def _validate_assessment(
        self,
        assessment: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        if assessment.get("assessment_type") != SUPPORTED_ASSESSMENT_TYPE:
            self._error(
                issues,
                "PV101",
                "assessment",
                "assessment_type",
                "目前僅支援 footwork。",
            )

        events = assessment.get("events")
        if not isinstance(events, list):
            return

        for index, event in enumerate(events):
            self._validate_required_fields(
                f"assessment.events[{index}]",
                event if isinstance(event, Mapping) else {},
                ASSESSMENT_EVENT_REQUIRED_FIELDS,
                issues,
            )

        event_count = assessment.get("event_count")
        if isinstance(event_count, int) and not isinstance(event_count, bool):
            if event_count != len(events):
                self._error(
                    issues,
                    "PV102",
                    "assessment",
                    "event_count",
                    f"event_count={event_count} 與 events 長度={len(events)} 不一致。",
                )

        event_ids = [
            event.get("event_id")
            for event in events
            if isinstance(event, Mapping)
        ]
        if event_ids and len(set(event_ids)) != len(event_ids):
            self._error(
                issues,
                "PV103",
                "assessment",
                "events.event_id",
                "event_id 不可重複。",
            )

    def _validate_coach(
        self,
        coach: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        status = coach.get("overall_status")
        if isinstance(status, str) and status not in VALID_COACH_STATUSES:
            self._error(
                issues,
                "PV201",
                "coach_evaluation",
                "overall_status",
                f"不支援的狀態：{status}",
            )

        rules = coach.get("rules")
        if not isinstance(rules, list):
            return

        rule_ids: list[Any] = []
        for index, rule in enumerate(rules):
            normalized = rule if isinstance(rule, Mapping) else {}
            self._validate_required_fields(
                f"coach_evaluation.rules[{index}]",
                normalized,
                COACH_RULE_REQUIRED_FIELDS,
                issues,
            )
            rule_ids.append(normalized.get("rule_id"))
            result = normalized.get("result")
            if isinstance(result, str) and result not in VALID_RULE_RESULTS:
                self._error(
                    issues,
                    "PV202",
                    "coach_evaluation",
                    f"rules[{index}].result",
                    f"不支援的 Rule Result：{result}",
                )

        if rule_ids and not unique_non_empty_strings(rule_ids):
            self._error(
                issues,
                "PV203",
                "coach_evaluation",
                "rules.rule_id",
                "rule_id 必須為不重複的非空字串。",
            )

        summary = coach.get("checklist_summary")
        if isinstance(summary, Mapping) and isinstance(rules, list):
            count_keys = (
                "pass_count",
                "fail_count",
                "needs_review_count",
                "not_evaluated_count",
            )
            counts = [summary.get(key) for key in count_keys]
            if all(isinstance(value, int) and not isinstance(value, bool) for value in counts):
                if sum(counts) != len(rules):
                    self._error(
                        issues,
                        "PV204",
                        "coach_evaluation",
                        "checklist_summary",
                        "Checklist 統計總數與 rules 長度不一致。",
                    )

    def _validate_report(
        self,
        report: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        summary = report.get("summary")
        if isinstance(summary, Mapping):
            status = summary.get("coach_status")
            if isinstance(status, str) and status not in VALID_COACH_STATUSES:
                self._error(
                    issues,
                    "PV301",
                    "analysis_report",
                    "summary.coach_status",
                    f"不支援的 Coach Status：{status}",
                )

        radar = report.get("radar_chart")
        if isinstance(radar, Mapping):
            labels = radar.get("labels")
            scores = radar.get("scores")
            if isinstance(labels, list) and isinstance(scores, list):
                if len(labels) != len(scores):
                    self._error(
                        issues,
                        "PV302",
                        "analysis_report",
                        "radar_chart",
                        "labels 與 scores 長度必須一致。",
                    )

    def _validate_review(
        self,
        review: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        status = review.get("review_status")
        if isinstance(status, str) and status not in VALID_REVIEW_STATUSES:
            self._error(
                issues,
                "PV401",
                "review_package",
                "review_status",
                f"不支援的 Review Status：{status}",
            )

        events = review.get("events")
        if not isinstance(events, list):
            return
        for index, event in enumerate(events):
            self._validate_required_fields(
                f"review_package.events[{index}]",
                event if isinstance(event, Mapping) else {},
                REVIEW_EVENT_REQUIRED_FIELDS,
                issues,
            )

    def _validate_cross_contracts(
        self,
        artifacts: Mapping[str, Mapping[str, Any]],
        issues: list[ValidationIssue],
    ) -> None:
        assessment = artifacts["assessment"]
        coach = artifacts["coach_evaluation"]
        report = artifacts["analysis_report"]
        review = artifacts["review_package"]

        self._require_equal_across(
            "assessment_id",
            {
                "assessment": assessment.get("assessment_id"),
                "coach_evaluation": coach.get("assessment_id"),
                "analysis_report": report.get("assessment_id"),
                "review_package": review.get("assessment_id"),
            },
            issues,
        )
        self._require_equal_across(
            "assessment_type",
            {
                "assessment": assessment.get("assessment_type"),
                "coach_evaluation": coach.get("assessment_type"),
                "analysis_report": report.get("assessment_type"),
                "review_package": review.get("assessment_type"),
            },
            issues,
        )
        self._require_equal_across(
            "engine_version",
            {
                "assessment": assessment.get("engine_version"),
                "coach_evaluation": coach.get("engine_version"),
                "analysis_report.meta": self._nested(report, "meta", "engine_version"),
                "review_package": review.get("engine_version"),
            },
            issues,
        )
        self._require_equal_across(
            "config_version",
            {
                "assessment": assessment.get("config_version"),
                "coach_evaluation": coach.get("config_version"),
                "analysis_report.meta": self._nested(report, "meta", "config_version"),
                "review_package": review.get("config_version"),
            },
            issues,
        )

        coach_status = coach.get("overall_status")
        report_coach_status = self._nested(report, "summary", "coach_status")
        if coach_status is not None and report_coach_status is not None:
            if coach_status != report_coach_status:
                self._error(
                    issues,
                    "PV503",
                    "cross_contract",
                    "overall_status",
                    "Coach overall_status 與 Report summary.coach_status 不一致。",
                )

        assessment_events = assessment.get("events")
        review_events = review.get("events")
        if isinstance(assessment_events, list) and isinstance(review_events, list):
            assessment_ids = [
                event.get("event_id")
                for event in assessment_events
                if isinstance(event, Mapping)
            ]
            review_ids = [
                event.get("event_id")
                for event in review_events
                if isinstance(event, Mapping)
            ]
            if assessment_ids != review_ids:
                self._error(
                    issues,
                    "PV504",
                    "cross_contract",
                    "events.event_id",
                    "Assessment 與 Review Package 的 Event 順序或 ID 不一致。",
                )

    def _require_equal_across(
        self,
        field: str,
        values: Mapping[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        present = {name: value for name, value in values.items() if value is not None}
        if len(present) < 2:
            return
        if len(set(present.values())) != 1:
            formatted = ", ".join(f"{name}={value!r}" for name, value in present.items())
            self._error(
                issues,
                "PV502",
                "cross_contract",
                field,
                f"跨模組欄位不一致：{formatted}",
            )

    def _build_report(
        self,
        artifacts: Mapping[str, Mapping[str, Any]],
        artifact_paths: Optional[Mapping[str, Path]],
        issues: Iterable[ValidationIssue],
    ) -> dict[str, Any]:
        issue_list = list(issues)
        error_count = sum(issue.severity == "ERROR" for issue in issue_list)
        warning_count = sum(issue.severity == "WARNING" for issue in issue_list)
        assessment_id = artifacts["assessment"].get("assessment_id")

        return {
            "schema_version": "1.0",
            "validator_version": self.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "assessment_id": assessment_id,
            "status": "PASS" if error_count == 0 else "FAIL",
            "summary": {
                "artifact_count": len(artifacts),
                "error_count": error_count,
                "warning_count": warning_count,
                "check_count": self._estimate_check_count(artifacts),
            },
            "artifacts": {
                name: {
                    "path": str(artifact_paths[name]) if artifact_paths and name in artifact_paths else None,
                    "present": bool(not artifact_paths or (name in artifact_paths and Path(artifact_paths[name]).exists())),
                }
                for name in artifacts
            },
            "issues": [issue.to_dict() for issue in issue_list],
        }

    @staticmethod
    def _estimate_check_count(artifacts: Mapping[str, Mapping[str, Any]]) -> int:
        return (
            len(ASSESSMENT_REQUIRED_FIELDS)
            + len(COACH_REQUIRED_FIELDS)
            + len(REPORT_REQUIRED_FIELDS)
            + len(REVIEW_REQUIRED_FIELDS)
            + len(artifacts.get("assessment", {}).get("events", []))
            + len(artifacts.get("coach_evaluation", {}).get("rules", []))
            + len(artifacts.get("review_package", {}).get("events", []))
            + 7
        )

    @staticmethod
    def _nested(source: Mapping[str, Any], *keys: str) -> Any:
        current: Any = source
        for key in keys:
            if not isinstance(current, Mapping):
                return None
            current = current.get(key)
        return current

    @staticmethod
    def _error(
        issues: list[ValidationIssue],
        code: str,
        artifact: str,
        field: Optional[str],
        message: str,
    ) -> None:
        issues.append(ValidationIssue("ERROR", code, artifact, field, message))
