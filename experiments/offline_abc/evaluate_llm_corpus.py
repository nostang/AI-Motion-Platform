#!/usr/bin/env python3
"""Create automatic checks and a human-review sheet for an LLM corpus run."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from benchmark_gemma4 import PROJECT_ROOT, REQUIRED_KEYS, _compact_report


SCORE_PATTERN = re.compile(r"(?:評分(?:為|是|高達)?|得分(?:為|是)?)\s*(\d+(?:\.\d+)?)\s*分")
DIRECT_VISUAL_CLAIMS = ("我看到", "影片中可以看到", "畫面顯示", "觀察到球拍", "觀察到羽球")
LIMITATION_TERMS = ("單鏡頭", "2D", "二維")
UNCERTAINTY_TERMS = ("不足", "無法", "尚未", "未評估", "僅能", "缺乏")
POSITIVE_LEVELS = {"GOOD", "EXCELLENT", "PASS"}


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _score_integrity(response_text: str, input_score: float | int | None) -> tuple[bool, list[float]]:
    mentions = [float(value) for value in SCORE_PATTERN.findall(response_text)]
    if input_score is None:
        return not mentions, mentions
    return all(abs(value - float(input_score)) <= 0.51 for value in mentions), mentions


def _positive_metric_tokens(score_breakdown: Any) -> set[str]:
    tokens: set[str] = set()
    if not isinstance(score_breakdown, dict):
        return tokens
    for key, value in score_breakdown.items():
        if isinstance(value, dict):
            if str(value.get("level") or "").upper() in POSITIVE_LEVELS:
                tokens.add(str(key))
            measurement_levels = value.get("measurement_levels")
            if isinstance(measurement_levels, dict):
                tokens.update(
                    str(metric)
                    for metric, level in measurement_levels.items()
                    if str(level).upper() in POSITIVE_LEVELS
                )
            tokens.update(_positive_metric_tokens(value))
    return tokens


def _evaluate_case(case: dict) -> dict:
    report_path = Path(case["report_path"])
    if not report_path.is_absolute():
        report_path = PROJECT_ROOT / report_path
    source = _compact_report(json.loads(report_path.read_text(encoding="utf-8")))
    response = case.get("response") if isinstance(case.get("response"), dict) else {}
    response_text = _text(response)
    response_priority = _text(response.get("priority", ""))
    response_strength = _text(response.get("strength", ""))
    source_priorities = [str(value) for value in source.get("improvement_priorities") or []]
    source_strengths = [str(value) for value in source.get("strengths") or []]
    positive_metrics = _positive_metric_tokens(source.get("score_breakdown"))
    if source_strengths:
        strength_grounded = any(value in response_strength for value in source_strengths)
    else:
        strength_grounded = (
            any(term in response_strength.lower() for term in ("無", "无", "none"))
            or any(metric in response_strength for metric in positive_metrics)
        )
    score_ok, score_mentions = _score_integrity(response_text, case.get("input_overall_score"))
    insufficient = (
        source["summary"].get("evaluation_status") == "INSUFFICIENT_EVIDENCE"
        or case.get("input_overall_score") is None
    )
    checks = {
        "schema_exact_keys": set(response) == REQUIRED_KEYS,
        "non_empty_required_values": all(bool(_text(response.get(key, "")).strip()) for key in REQUIRED_KEYS),
        "all_priorities_grounded": all(value in response_priority for value in source_priorities),
        "strength_grounded_or_explicitly_none": strength_grounded,
        "score_claim_integrity": score_ok,
        "limitation_acknowledged": any(term in _text(response.get("caution", "")) for term in LIMITATION_TERMS),
        "no_direct_visual_claim": not any(term in response_text for term in DIRECT_VISUAL_CLAIMS),
        "insufficient_evidence_respected": not insufficient
        or any(term in response_text for term in UNCERTAINTY_TERMS),
        "traditional_chinese_basic_check": "无" not in response_text,
    }
    return {
        "case_id": case["case_id"],
        "evidence_kind": case.get("evidence_kind"),
        "motion": case.get("motion"),
        "scenario": case.get("scenario"),
        "input_score": case.get("input_overall_score"),
        "input_status": source["summary"].get("evaluation_status"),
        "input_strengths": source_strengths,
        "positive_score_metrics": sorted(positive_metrics),
        "input_priorities": source_priorities,
        "score_mentions": score_mentions,
        "response": response,
        "checks": checks,
        "automatic_pass": all(checks.values()),
    }


def _aggregate(cases: list[dict]) -> dict:
    check_names = list(cases[0]["checks"]) if cases else []
    return {
        "case_count": len(cases),
        "automatic_all_checks_pass_rate": round(
            sum(case["automatic_pass"] for case in cases) / len(cases), 3
        ) if cases else None,
        "check_pass_rates": {
            name: round(sum(case["checks"][name] for case in cases) / len(cases), 3)
            for name in check_names
        },
    }


def _write_review_csv(path: Path, cases: list[dict]) -> None:
    fields = [
        "blind_output_id", "case_id", "evidence_kind", "motion", "scenario",
        "input_score", "input_status", "input_strengths", "input_priorities",
        "output_summary", "output_strength", "output_priority", "output_drill", "output_caution",
        "auto_all_checks_pass", "human_grounding_1_to_5", "human_helpfulness_1_to_5",
        "human_clarity_1_to_5", "human_hallucination_yes_no", "reviewer_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        for index, case in enumerate(cases, start=1):
            response = case["response"]
            writer.writerow(
                {
                    "blind_output_id": f"OUT-{index:02d}",
                    "case_id": case["case_id"],
                    "evidence_kind": case["evidence_kind"],
                    "motion": case["motion"],
                    "scenario": case["scenario"],
                    "input_score": case["input_score"],
                    "input_status": case["input_status"],
                    "input_strengths": _text(case["input_strengths"]),
                    "input_priorities": _text(case["input_priorities"]),
                    "output_summary": _text(response.get("summary", "")),
                    "output_strength": _text(response.get("strength", "")),
                    "output_priority": _text(response.get("priority", "")),
                    "output_drill": _text(response.get("drill", "")),
                    "output_caution": _text(response.get("caution", "")),
                    "auto_all_checks_pass": case["automatic_pass"],
                    "human_grounding_1_to_5": "",
                    "human_helpfulness_1_to_5": "",
                    "human_clarity_1_to_5": "",
                    "human_hallucination_yes_no": "",
                    "reviewer_notes": "",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-csv", type=Path, required=True)
    args = parser.parse_args()

    run = json.loads(args.input.read_text(encoding="utf-8"))
    cases = [_evaluate_case(case) for case in run["cases"]]
    evidence_kinds = sorted({case["evidence_kind"] for case in cases})
    result = {
        "evaluation": "automatic_contract_and_grounding_checks_not_human_semantic_review",
        "source_run": str(args.input),
        "overall": _aggregate(cases),
        "by_evidence_kind": {
            kind: _aggregate([case for case in cases if case["evidence_kind"] == kind])
            for kind in evidence_kinds
        },
        "failed_cases": [case for case in cases if not case["automatic_pass"]],
        "cases": cases,
        "human_review": {
            "status": "pending",
            "review_sheet": str(args.review_csv),
            "required_dimensions": ["grounding", "helpfulness", "clarity", "hallucination"],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_review_csv(args.review_csv, cases)
    print(json.dumps({"overall": result["overall"], "failed_case_count": len(result["failed_cases"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
