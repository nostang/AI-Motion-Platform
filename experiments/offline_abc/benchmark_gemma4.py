#!/usr/bin/env python3
"""Benchmark local Gemma 4 coaching copy from existing Motion report JSON."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
import urllib.parse
import urllib.request
from pathlib import Path


REQUIRED_KEYS = {"summary", "strength", "priority", "drill", "caution"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _compact_report(report: dict) -> dict:
    summary = report.get("summary") or {}
    highlights = report.get("highlights") or report.get("result_summary", {}).get("highlights") or {}
    return {
        "assessment_type": report.get("assessment_type"),
        "summary": {
            "evaluation_status": summary.get("evaluation_status"),
            "overall_score": summary.get("overall_score"),
            "system_confidence": summary.get("system_confidence"),
        },
        "score_breakdown": report.get("score_breakdown") or report.get("skill_score") or {},
        "strengths": highlights.get("strengths") or [],
        "improvement_priorities": highlights.get("improvement_priorities") or [],
        "limitations": (report.get("limitations") or report.get("review", {}).get("limitations") or [])[:6],
    }


def _lean_compact_report(report: dict) -> dict:
    """Keep coaching evidence while removing transport-irrelevant rule metadata."""

    compact = _compact_report(report)
    lean_scores = {}
    for name, value in compact["score_breakdown"].items():
        if isinstance(value, dict):
            selected = {
                key: value.get(key)
                for key in ("score", "level", "status")
                if value.get(key) is not None
            }
            lean_scores[name] = selected
        else:
            lean_scores[name] = value
    compact["score_breakdown"] = lean_scores
    compact["limitations"] = compact["limitations"][:4]
    return compact


def _minimal_compact_report(report: dict) -> dict:
    """Diagnostic/common profile with only top-level coaching evidence."""

    compact = _compact_report(report)
    compact["score_breakdown"] = {}
    compact["limitations"] = compact["limitations"][:2]
    return compact


def _select_compact_report(report: dict, profile: str) -> dict:
    if profile == "full":
        return _compact_report(report)
    if profile == "lean":
        return _lean_compact_report(report)
    if profile == "minimal":
        return _minimal_compact_report(report)
    raise ValueError(f"Unsupported compact profile: {profile}")


def _prompt(compact: dict, version: str = "v1") -> str:
    base = (
        "你是羽球動作分析報告的文字說明器。只能根據下列 MediaPipe 與規則引擎的結構化結果撰寫，"
        "不可修改分數、不可聲稱看見球拍或羽球、不可做醫療診斷。請用繁體中文回傳 JSON，且只含："
        "summary（2句）、strength、priority、drill（可實行練習）、caution（單鏡頭2D限制）。"
    )
    if version == "v1":
        instructions = ""
    elif version == "v2":
        instructions = (
            "必須剛好使用這五個 key，不得新增、改名或省略。格式範例："
            '{"summary":"","strength":"","priority":[],"drill":[],"caution":""}。'
            "若輸入沒有優點，strength 填『無明確優點』；若沒有改善項目，priority 使用空陣列。"
        )
    elif version == "v3":
        return (
            "依JSON用繁中回羽球教練JSON，只含summary（2句）、strength、priority、drill、caution；"
            "summary/caution為字串，strength/priority/drill為字串陣列。不改分、不假裝看見球拍/羽球、"
            "不做醫療診斷。輸入的snake_case優點/"
            "改善ID須原樣放在中文後括號；兩類勿互換，無項目用[]；caution須寫單鏡頭2D限制。\n"
            + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        )
    else:
        raise ValueError(f"Unsupported prompt version: {version}")
    return base + instructions + "\n" + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))


def _call_ollama(endpoint: str, model: str, prompt: str, num_gpu: int | None = None) -> dict:
    options = {"temperature": 0, "seed": 7, "num_predict": 320}
    if num_gpu is not None:
        options["num_gpu"] = num_gpu
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "think": False,
            "options": options,
            "keep_alive": "10m",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        payload = json.load(response)
    payload["client_wall_seconds"] = time.perf_counter() - started
    return payload


def _ollama_process(endpoint: str, model: str) -> dict:
    """Read Ollama's local resident-model accounting; never contacts a cloud API."""

    parsed = urllib.parse.urlsplit(endpoint)
    ps_endpoint = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/api/ps", "", ""))
    with urllib.request.urlopen(ps_endpoint, timeout=10) as response:
        payload = json.load(response)
    for loaded in payload.get("models", []):
        if loaded.get("name") == model or loaded.get("model") == model:
            return {
                "resident_size_bytes": int(loaded.get("size") or 0),
                "resident_vram_bytes": int(loaded.get("size_vram") or 0),
                "quantization_level": (loaded.get("details") or {}).get("quantization_level"),
            }
    return {"resident_size_bytes": 0, "resident_vram_bytes": 0, "quantization_level": None}


def _validate(response_text: str, compact: dict) -> dict:
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return {"json_valid": False, "required_keys": False, "priority_grounded": False, "caution_present": False}
    priorities = compact.get("improvement_priorities") or []
    response_priority = str(parsed.get("priority", ""))
    return {
        "json_valid": True,
        "required_keys": REQUIRED_KEYS.issubset(parsed),
        "priority_grounded": not priorities or any(str(item) in response_priority for item in priorities),
        "caution_present": bool(str(parsed.get("caution", "")).strip()),
    }


def _case_id(report_path: Path, report: dict) -> str:
    return str(report.get("video_id") or report.get("assessment_id") or report_path.parent.name)


def _parse_response(response_text: str) -> dict | None:
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _manifest_reports(manifest_path: Path) -> tuple[list[Path], dict[str, dict]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reports = []
    metadata = {}
    for case in [*(manifest.get("real_cases") or []), *(manifest.get("synthetic_cases") or [])]:
        report_path_text = case.get("report_path")
        if not report_path_text or case.get("status") not in {"completed", "generated"}:
            continue
        report_path = Path(report_path_text)
        if not report_path.is_absolute():
            report_path = PROJECT_ROOT / report_path
        reports.append(report_path)
        metadata[str(report_path.resolve())] = {
            "case_id": case.get("case_id"),
            "evidence_kind": case.get("evidence_kind"),
            "motion": case.get("motion"),
            "scenario": case.get("scenario"),
        }
    return reports, metadata


def _aggregate_cases(cases: list[dict]) -> dict:
    latencies = [case["client_wall_seconds"] for case in cases]
    token_rates = [case["tokens_per_second"] for case in cases if case["tokens_per_second"]]
    return {
        "case_count": len(cases),
        "mean_wall_seconds": round(statistics.fmean(latencies), 4),
        "p50_wall_seconds": round(_percentile(latencies, 0.5) or 0.0, 4),
        "p95_wall_seconds": round(_percentile(latencies, 0.95) or 0.0, 4),
        "mean_tokens_per_second": round(statistics.fmean(token_rates), 3) if token_rates else None,
        "success_rate": round(sum(case["success"] for case in cases) / len(cases), 3),
        "json_valid_rate": round(sum(case["checks"]["json_valid"] for case in cases) / len(cases), 3),
        "required_keys_rate": round(sum(case["checks"]["required_keys"] for case in cases) / len(cases), 3),
        "priority_grounded_rate": round(
            sum(case["checks"]["priority_grounded"] for case in cases) / len(cases), 3
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, action="append", default=[])
    parser.add_argument("--manifest", type=Path, help="Use every completed/generated report in a corpus manifest")
    parser.add_argument("--model", default="gemma4:e2b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--prompt-version", choices=("v1", "v2", "v3"), default="v1")
    parser.add_argument("--compact-profile", choices=("full", "lean", "minimal"), default="full")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--num-gpu",
        type=int,
        help="Ollama GPU layer override; use 0 for a reproducible CPU-only comparison",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report_paths = list(args.report)
    corpus_metadata: dict[str, dict] = {}
    if args.manifest:
        manifest_reports, corpus_metadata = _manifest_reports(args.manifest)
        report_paths.extend(manifest_reports)
    report_paths = list(dict.fromkeys(path.resolve() for path in report_paths))
    if not report_paths:
        parser.error("provide at least one --report or --manifest")

    cases = []
    for report_path in report_paths:
        report = json.loads(report_path.read_text())
        compact = _select_compact_report(report, args.compact_profile)
        metadata = corpus_metadata.get(str(report_path.resolve()), {})
        for repeat in range(args.repeats):
            raw = _call_ollama(
                args.endpoint,
                args.model,
                _prompt(compact, args.prompt_version),
                args.num_gpu,
            )
            eval_duration = int(raw.get("eval_duration") or 0)
            eval_count = int(raw.get("eval_count") or 0)
            response_text = raw.get("response", "")
            checks = _validate(response_text, compact)
            cases.append(
                {
                    "case_id": metadata.get("case_id") or _case_id(report_path, report),
                    "evidence_kind": metadata.get("evidence_kind") or "unspecified_report",
                    "motion": metadata.get("motion") or compact.get("assessment_type"),
                    "scenario": metadata.get("scenario"),
                    "report_path": str(report_path.relative_to(PROJECT_ROOT)) if report_path.is_relative_to(PROJECT_ROOT) else str(report_path),
                    "repeat": repeat + 1,
                    "client_wall_seconds": round(raw["client_wall_seconds"], 4),
                    "load_seconds": round(int(raw.get("load_duration") or 0) / 1e9, 4),
                    "prompt_tokens": int(raw.get("prompt_eval_count") or 0),
                    "output_tokens": eval_count,
                    "tokens_per_second": round(eval_count / (eval_duration / 1e9), 3) if eval_duration else None,
                    "input_overall_score": compact["summary"]["overall_score"],
                    "checks": checks,
                    "success": all(
                        checks[key]
                        for key in ("json_valid", "required_keys", "caution_present")
                    ),
                    "response": _parse_response(response_text),
                }
            )

    resource = _ollama_process(args.endpoint, args.model)
    by_evidence_kind = {}
    for evidence_kind in sorted({case["evidence_kind"] for case in cases}):
        selected = [case for case in cases if case["evidence_kind"] == evidence_kind]
        by_evidence_kind[evidence_kind] = _aggregate_cases(selected)

    payload = {
        "benchmark": "local-gemma4-motion-explanation",
        "model": args.model,
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "transport": "Ollama localhost",
            "num_gpu_override": args.num_gpu,
            "corpus_manifest": str(args.manifest) if args.manifest else None,
            "prompt_version": args.prompt_version,
            "compact_profile": args.compact_profile,
        },
        "resource": resource,
        "cases": cases,
        "aggregate": _aggregate_cases(cases),
        "aggregate_by_evidence_kind": by_evidence_kind,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
