#!/usr/bin/env python3
"""Safely benchmark Gemini on the fixed A/B JSON corpus.

Dry-run is the default. A real network request is possible only with both
``--execute`` and an isolated ``GEMINI_API_KEY`` environment variable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from benchmark_gemma4 import (
    PROJECT_ROOT,
    REQUIRED_KEYS,
    _manifest_reports,
    _parse_response,
    _percentile,
    _prompt,
    _select_compact_report,
    _validate,
)


DEFAULT_MODEL = "gemini-3.5-flash-lite"
API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")
INPUT_USD_PER_MILLION = 0.30
OUTPUT_USD_PER_MILLION = 2.50
MAX_OUTPUT_TOKENS = 320

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strength": {"type": "array", "items": {"type": "string"}},
        "priority": {"type": "array", "items": {"type": "string"}},
        "drill": {"type": "array", "items": {"type": "string"}},
        "caution": {"type": "string"},
    },
    "required": sorted(REQUIRED_KEYS),
    "additionalProperties": False,
}


def _request_payload(prompt: str) -> dict:
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
            "responseJsonSchema": OUTPUT_SCHEMA,
        },
    }


def _estimate_input_tokens(prompt: str) -> int:
    """Return a deliberately conservative preflight estimate for mixed CJK JSON."""

    byte_count = len(prompt.encode("utf-8"))
    return max(1, (byte_count + 1) // 2)


def _paid_tier_equivalent_cost_usd(input_tokens: int, billable_output_tokens: int) -> float:
    return (
        input_tokens * INPUT_USD_PER_MILLION
        + billable_output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000


def _schema_types_valid(response: dict | None) -> bool:
    if not isinstance(response, dict) or set(response) != REQUIRED_KEYS:
        return False
    return (
        isinstance(response["summary"], str)
        and isinstance(response["strength"], list)
        and all(isinstance(item, str) for item in response["strength"])
        and isinstance(response["priority"], list)
        and all(isinstance(item, str) for item in response["priority"])
        and isinstance(response["drill"], list)
        and all(isinstance(item, str) for item in response["drill"])
        and isinstance(response["caution"], str)
    )


def _extract_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini response did not contain a candidate")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(str(part.get("text") or "") for part in parts)
    if not text:
        raise ValueError("Gemini response did not contain text")
    return text


def _usage(payload: dict) -> dict:
    usage = payload.get("usageMetadata") or {}
    prompt_tokens = int(usage.get("promptTokenCount") or 0)
    candidate_tokens = int(usage.get("candidatesTokenCount") or 0)
    thought_tokens = int(usage.get("thoughtsTokenCount") or 0)
    total_tokens = int(usage.get("totalTokenCount") or 0)
    # Gemini pricing counts thinking tokens as output. total - prompt is the
    # safest provider-reported upper bound when cached-token details vary.
    billable_output_tokens = max(
        candidate_tokens + thought_tokens,
        total_tokens - prompt_tokens,
        0,
    )
    return {
        "prompt_tokens": prompt_tokens,
        "candidate_tokens": candidate_tokens,
        "thought_tokens": thought_tokens,
        "total_tokens": total_tokens,
        "billable_output_tokens": billable_output_tokens,
    }


def _call_gemini(model: str, api_key: str, prompt: str, timeout: float) -> dict:
    if not MODEL_PATTERN.fullmatch(model):
        raise ValueError("model id contains unsupported characters")
    request = urllib.request.Request(
        API_ENDPOINT.format(model=model),
        data=json.dumps(_request_payload(prompt), ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return {"payload": payload, "client_wall_seconds": time.perf_counter() - started}


def _load_cases(
    manifest: Path,
    selected_case_ids: set[str],
    compact_profile: str,
    prompt_version: str,
) -> list[dict]:
    report_paths, metadata = _manifest_reports(manifest)
    cases = []
    for report_path in report_paths:
        item = metadata[str(report_path.resolve())]
        case_id = str(item["case_id"])
        if selected_case_ids and case_id not in selected_case_ids:
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        compact = _select_compact_report(report, compact_profile)
        prompt = _prompt(compact, prompt_version)
        cases.append(
            {
                **item,
                "case_id": case_id,
                "report_path": (
                    str(report_path.relative_to(PROJECT_ROOT))
                    if report_path.is_relative_to(PROJECT_ROOT)
                    else str(report_path)
                ),
                "compact": compact,
                "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "estimated_input_tokens": _estimate_input_tokens(prompt),
            }
        )
    missing = selected_case_ids - {case["case_id"] for case in cases}
    if missing:
        raise ValueError(f"unknown case id(s): {', '.join(sorted(missing))}")
    return cases


def _preflight(
    cases: list[dict],
    model: str,
    compact_profile: str = "full",
    prompt_version: str = "v1",
) -> dict:
    estimated_input_tokens = sum(case["estimated_input_tokens"] for case in cases)
    maximum_output_tokens = len(cases) * MAX_OUTPUT_TOKENS
    return {
        "execution_evidence_kind": "cloud_api_dry_run_not_measurement",
        "provider": "Google Gemini API",
        "model": model,
        "compact_profile": compact_profile,
        "prompt_version": prompt_version,
        "case_count": len(cases),
        "data_boundary": "compact structured motion JSON only; no video upload",
        "estimated_input_tokens_upper_bound": estimated_input_tokens,
        "maximum_output_tokens": maximum_output_tokens,
        "estimated_maximum_cost_usd": round(
            _paid_tier_equivalent_cost_usd(estimated_input_tokens, maximum_output_tokens), 6
        ),
        "pricing": {
            "input_usd_per_million_tokens": INPUT_USD_PER_MILLION,
            "output_including_thinking_usd_per_million_tokens": OUTPUT_USD_PER_MILLION,
            "checked_on": "2026-09-26",
            "source": "https://ai.google.dev/gemini-api/docs/pricing",
        },
        "cases": [
            {
                key: case.get(key)
                for key in (
                    "case_id",
                    "evidence_kind",
                    "motion",
                    "scenario",
                    "report_path",
                    "prompt_sha256",
                    "estimated_input_tokens",
                )
            }
            for case in cases
        ],
    }


def _aggregate(cases: list[dict]) -> dict:
    completed = [case for case in cases if case.get("response") is not None]
    if not completed:
        return {
            "case_count": len(cases),
            "completed_count": 0,
            "success_rate": None,
            "total_estimated_paid_tier_cost_usd": 0.0,
        }
    latencies = [case["client_wall_seconds"] for case in completed]
    return {
        "case_count": len(cases),
        "completed_count": len(completed),
        "mean_wall_seconds": round(statistics.fmean(latencies), 4),
        "p50_wall_seconds": round(_percentile(latencies, 0.5) or 0.0, 4),
        "p95_wall_seconds": round(_percentile(latencies, 0.95) or 0.0, 4),
        "success_rate": round(sum(case["success"] for case in completed) / len(completed), 3),
        "schema_types_valid_rate": round(
            sum(case["checks"]["provider_schema_types"] for case in completed) / len(completed), 3
        ),
        "priority_grounded_rate": round(
            sum(case["checks"]["priority_grounded"] for case in completed) / len(completed), 3
        ),
        "total_estimated_paid_tier_cost_usd": round(
            sum(case["estimated_paid_tier_cost_usd"] for case in completed), 8
        ),
    }


def _safe_error(error: Exception) -> dict:
    if isinstance(error, urllib.error.HTTPError):
        detail = None
        raw_body = b""
        try:
            raw_body = error.read(4096)
            body = json.loads(raw_body.decode("utf-8", errors="replace"))
            provider_error = body.get("error") if isinstance(body, dict) else None
            if isinstance(provider_error, dict):
                detail = {
                    key: provider_error.get(key)
                    for key in ("code", "message", "status")
                    if provider_error.get(key) is not None
                }
        except (json.JSONDecodeError, OSError, UnicodeError):
            body_text = raw_body.decode("utf-8", errors="replace").strip()
            detail = {"raw_body": body_text[:2000]} if body_text else None
        return {
            "type": "HTTPError",
            "status": error.code,
            "reason": str(error.reason),
            "content_type": error.headers.get("Content-Type") if error.headers else None,
            "provider_error": detail,
        }
    if isinstance(error, urllib.error.URLError):
        return {"type": "URLError", "reason": str(error.reason)}
    return {"type": type(error).__name__, "reason": str(error)}


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--compact-profile", choices=("full", "lean", "minimal"), default="full"
    )
    parser.add_argument("--prompt-version", choices=("v1", "v2", "v3"), default="v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Actually call the isolated cloud API")
    parser.add_argument(
        "--billing-tier-label",
        default="unknown_not_read_from_api",
        help="Evidence label only; cost remains a paid-tier price equivalent, not an invoice",
    )
    parser.add_argument("--max-estimated-usd", type=float, default=0.05)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument(
        "--minimum-request-interval-seconds",
        type=float,
        default=0.0,
        help="Minimum start-to-start interval for respecting project RPM limits",
    )
    args = parser.parse_args()

    if args.minimum_request_interval_seconds < 0:
        parser.error("minimum request interval must not be negative")
    if not MODEL_PATTERN.fullmatch(args.model):
        parser.error("model id contains unsupported characters")
    cases = _load_cases(
        args.manifest.resolve(),
        set(args.case_id),
        args.compact_profile,
        args.prompt_version,
    )
    if not cases:
        parser.error("manifest did not contain any runnable cases")
    preflight = _preflight(cases, args.model, args.compact_profile, args.prompt_version)
    if preflight["estimated_maximum_cost_usd"] > args.max_estimated_usd:
        parser.error(
            f"estimated maximum US${preflight['estimated_maximum_cost_usd']:.6f} exceeds "
            f"the US${args.max_estimated_usd:.6f} safety cap"
        )

    if not args.execute:
        payload = {
            "benchmark": "cloud-gemini-motion-explanation-preflight",
            **preflight,
            "network_request_count": 0,
            "actual_cost_usd": 0.0,
            "next_step": "provide an isolated GEMINI_API_KEY and add --execute",
        }
        _write(args.output, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        parser.error("--execute requires an isolated GEMINI_API_KEY environment variable")

    results = []
    errors = []
    previous_request_started = None
    for case in cases:
        if previous_request_started is not None:
            remaining = args.minimum_request_interval_seconds - (
                time.monotonic() - previous_request_started
            )
            if remaining > 0:
                time.sleep(remaining)
        previous_request_started = time.monotonic()
        try:
            raw = _call_gemini(args.model, api_key, case["prompt"], args.timeout)
            response_text = _extract_text(raw["payload"])
            response = _parse_response(response_text)
            checks = _validate(response_text, case["compact"])
            checks["provider_schema_types"] = _schema_types_valid(response)
            usage = _usage(raw["payload"])
            results.append(
                {
                    **{
                        key: case.get(key)
                        for key in (
                            "case_id",
                            "evidence_kind",
                            "motion",
                            "scenario",
                            "report_path",
                            "prompt_sha256",
                        )
                    },
                    "input_overall_score": case["compact"]["summary"]["overall_score"],
                    "client_wall_seconds": round(raw["client_wall_seconds"], 4),
                    **usage,
                    "estimated_paid_tier_cost_usd": round(
                        _paid_tier_equivalent_cost_usd(
                            usage["prompt_tokens"], usage["billable_output_tokens"]
                        ),
                        8,
                    ),
                    "finish_reason": (raw["payload"].get("candidates") or [{}])[0].get("finishReason"),
                    "checks": checks,
                    "success": all(
                        checks[key]
                        for key in (
                            "json_valid",
                            "required_keys",
                            "caution_present",
                            "provider_schema_types",
                        )
                    ),
                    "response": response,
                }
            )
        except Exception as error:  # keep partial evidence without leaking secrets
            safe_error = _safe_error(error)
            errors.append({"case_id": case["case_id"], **safe_error})
            if safe_error.get("status") in {400, 401, 403}:
                break

    payload = {
        "benchmark": "cloud-gemini-motion-explanation",
        "execution_evidence_kind": "cloud_api_measurement",
        "provider": "Google Gemini API",
        "model": args.model,
        "billing_tier_label": args.billing_tier_label,
        "cost_semantics": "paid-tier price equivalent from token usage; not an observed invoice",
        "minimum_request_interval_seconds": args.minimum_request_interval_seconds,
        "data_boundary": preflight["data_boundary"],
        "preflight": preflight,
        "network_request_count": len(results) + len(errors),
        "cases": results,
        "errors": errors,
        "aggregate": _aggregate(results),
    }
    _write(args.output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
