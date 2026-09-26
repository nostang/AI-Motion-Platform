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


def _prompt(compact: dict) -> str:
    return (
        "你是羽球動作分析報告的文字說明器。只能根據下列 MediaPipe 與規則引擎的結構化結果撰寫，"
        "不可修改分數、不可聲稱看見球拍或羽球、不可做醫療診斷。請用繁體中文回傳 JSON，且只含："
        "summary（2句）、strength、priority、drill（可實行練習）、caution（單鏡頭2D限制）。\n"
        + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    )


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, action="append", required=True)
    parser.add_argument("--model", default="gemma4:e2b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--num-gpu",
        type=int,
        help="Ollama GPU layer override; use 0 for a reproducible CPU-only comparison",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = []
    for report_path in args.report:
        report = json.loads(report_path.read_text())
        compact = _compact_report(report)
        for repeat in range(args.repeats):
            raw = _call_ollama(args.endpoint, args.model, _prompt(compact), args.num_gpu)
            eval_duration = int(raw.get("eval_duration") or 0)
            eval_count = int(raw.get("eval_count") or 0)
            response_text = raw.get("response", "")
            checks = _validate(response_text, compact)
            cases.append(
                {
                    "case_id": _case_id(report_path, report),
                    "report_path": str(report_path),
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
    token_rates = [case["tokens_per_second"] for case in cases if case["tokens_per_second"]]

    payload = {
        "benchmark": "local-gemma4-motion-explanation",
        "model": args.model,
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "transport": "Ollama localhost",
            "num_gpu_override": args.num_gpu,
        },
        "resource": resource,
        "cases": cases,
        "aggregate": {
            "case_count": len(cases),
            "mean_wall_seconds": round(statistics.fmean(case["client_wall_seconds"] for case in cases), 4),
            "mean_tokens_per_second": round(statistics.fmean(token_rates), 3) if token_rates else None,
            "success_rate": round(sum(case["success"] for case in cases) / len(cases), 3),
            "json_valid_rate": round(sum(case["checks"]["json_valid"] for case in cases) / len(cases), 3),
            "required_keys_rate": round(sum(case["checks"]["required_keys"] for case in cases) / len(cases), 3),
            "priority_grounded_rate": round(sum(case["checks"]["priority_grounded"] for case in cases) / len(cases), 3),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
