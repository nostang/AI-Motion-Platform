#!/usr/bin/env python3
"""Apply deterministic normalization, validation, and safe fallback to a local LLM run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from benchmark_gemma4 import PROJECT_ROOT, REQUIRED_KEYS, _select_compact_report
from evaluate_llm_corpus import _evaluate_case


STRING_FIELDS = ("summary", "caution")
LIST_FIELDS = ("strength", "priority", "drill")


def _normalize_response(response: Any) -> tuple[dict, list[str]]:
    source = response if isinstance(response, dict) else {}
    normalized: dict[str, Any] = {}
    changes: list[str] = []

    for field in STRING_FIELDS:
        value = source.get(field, "")
        if isinstance(value, str):
            normalized[field] = value
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            normalized[field] = " ".join(item.strip() for item in value if item.strip())
            changes.append(f"{field}:string_list_to_string")
        else:
            normalized[field] = ""
            changes.append(f"{field}:unsupported_to_empty_string")

    for field in LIST_FIELDS:
        value = source.get(field, [])
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            normalized[field] = value
        elif isinstance(value, str):
            normalized[field] = [value] if value.strip() else []
            changes.append(f"{field}:string_to_string_list")
        else:
            normalized[field] = []
            changes.append(f"{field}:unsupported_to_empty_list")

    extra_keys = sorted(set(source) - REQUIRED_KEYS)
    if extra_keys:
        changes.append("removed_extra_keys:" + ",".join(extra_keys))
    return normalized, changes


def _load_compact(case: dict, compact_profile: str) -> dict:
    report_path = Path(case["report_path"])
    if not report_path.is_absolute():
        report_path = PROJECT_ROOT / report_path
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return _select_compact_report(report, compact_profile)


def _safe_fallback(case: dict, compact_profile: str) -> dict:
    compact = _load_compact(case, compact_profile)
    summary = compact.get("summary") or {}
    status = summary.get("evaluation_status")
    score = summary.get("overall_score")
    motion = compact.get("assessment_type") or case.get("motion") or "動作"
    strengths = [str(item) for item in compact.get("strengths") or []]
    priorities = [str(item) for item in compact.get("improvement_priorities") or []]

    if status == "INSUFFICIENT_EVIDENCE" or score is None:
        summary_text = "現有資料不足，無法可靠評估這次動作；請補充較完整且清楚的影片。"
    else:
        summary_text = f"本次{motion}評估已完成，規則引擎的整體評分為{score}分；以下內容只整理既有結果。"

    strength_text = (
        [f"規則引擎記錄的優點（{item}）" for item in strengths]
        if strengths
        else ["無明確優點：輸入未提供可確認的 strengths 項目"]
    )
    priority_text = (
        [f"優先改善（{item}）" for item in priorities]
        if priorities
        else ["無需新增改善項目：輸入未提供 improvement_priorities"]
    )
    drill_text = (
        [f"針對 {item} 進行分段慢速練習，並依原規則結果複查。" for item in priorities]
        if priorities
        else ["維持基礎動作，待取得更完整資料後再調整練習。"]
    )
    return {
        "summary": summary_text,
        "strength": strength_text,
        "priority": priority_text,
        "drill": drill_text,
        "caution": "本說明僅根據單攝影機 2D MediaPipe 與規則結果，未直接辨識羽球或球拍。",
    }


def apply_guardrails(run: dict) -> dict:
    compact_profile = (run.get("runtime") or {}).get("compact_profile") or "full"
    processed_cases = []
    raw_pass_count = 0
    normalized_pass_count = 0
    fallback_count = 0

    for source_case in run["cases"]:
        raw_case = {**source_case, "response": source_case.get("response")}
        raw_evaluation = _evaluate_case(raw_case, compact_profile)
        raw_pass_count += int(raw_evaluation["automatic_pass"])

        normalized, changes = _normalize_response(source_case.get("response"))
        normalized_case = {**source_case, "response": normalized}
        normalized_evaluation = _evaluate_case(normalized_case, compact_profile)
        normalized_pass = normalized_evaluation["automatic_pass"]
        normalized_pass_count += int(normalized_pass)

        fallback_used = not normalized_pass
        final_response = _safe_fallback(source_case, compact_profile) if fallback_used else normalized
        final_case = {**source_case, "response": final_response}
        final_evaluation = _evaluate_case(final_case, compact_profile)
        if not final_evaluation["automatic_pass"]:
            raise RuntimeError(f"safe fallback did not pass for {source_case['case_id']}")
        fallback_count += int(fallback_used)
        processed_cases.append(
            {
                **source_case,
                "raw_response": source_case.get("response"),
                "response": final_response,
                "guardrail": {
                    "normalization_changes": changes,
                    "raw_automatic_pass": raw_evaluation["automatic_pass"],
                    "normalized_automatic_pass": normalized_pass,
                    "fallback_used": fallback_used,
                    "normalized_failed_checks": [
                        name
                        for name, passed in normalized_evaluation["checks"].items()
                        if not passed
                    ],
                    "final_automatic_pass": True,
                },
            }
        )

    case_count = len(processed_cases)
    return {
        **run,
        "benchmark": "local-gemma4-motion-explanation-with-deterministic-guardrails",
        "guardrail_policy": {
            "normalization": "only deterministic string/list coercion and extra-key removal",
            "validation": "same automatic contract and grounding evaluator as A/B comparison",
            "fallback": "deterministic template from the original compact report; no LLM retry",
            "model_quality_note": "fallback success is product pipeline reliability, not raw model quality",
        },
        "cases": processed_cases,
        "guardrail_aggregate": {
            "case_count": case_count,
            "raw_automatic_pass_rate": round(raw_pass_count / case_count, 3),
            "normalized_automatic_pass_rate": round(normalized_pass_count / case_count, 3),
            "fallback_count": fallback_count,
            "fallback_rate": round(fallback_count / case_count, 3),
            "final_automatic_pass_rate": 1.0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    run = json.loads(args.input.read_text(encoding="utf-8"))
    result = apply_guardrails(run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["guardrail_aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
