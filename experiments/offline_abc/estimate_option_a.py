#!/usr/bin/env python3
"""Create a reproducible *estimate* for option A without calling cloud services."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


DEFAULT_INPUT_USD_PER_MILLION = 0.30
DEFAULT_OUTPUT_USD_PER_MILLION = 2.50
DEFAULT_CPU_USD_PER_SECOND = 0.000018
DEFAULT_MEMORY_GIB_USD_PER_SECOND = 0.000002


def calculate_estimate(
    mediapipe: dict,
    gemma: dict,
    monthly_analyses: int,
    input_usd_per_million: float = DEFAULT_INPUT_USD_PER_MILLION,
    output_usd_per_million: float = DEFAULT_OUTPUT_USD_PER_MILLION,
    cpu_usd_per_second: float = DEFAULT_CPU_USD_PER_SECOND,
    memory_gib_usd_per_second: float = DEFAULT_MEMORY_GIB_USD_PER_SECOND,
) -> dict:
    cases = gemma["cases"]
    mean_input_tokens = statistics.fmean(case["prompt_tokens"] for case in cases)
    mean_output_tokens = statistics.fmean(case["output_tokens"] for case in cases)
    llm_per_analysis = (
        mean_input_tokens * input_usd_per_million
        + mean_output_tokens * output_usd_per_million
    ) / 1_000_000

    # This intentionally uses local wall time only as a transparent scenario
    # input. It is not a claim about Cloud Run hardware performance.
    media_seconds = float(mediapipe["aggregate"]["mean_wall_seconds"])
    peak_gib = float(mediapipe["runs"][0]["peak_rss_mb"]) / 1024
    compute_per_analysis = media_seconds * (
        cpu_usd_per_second + peak_gib * memory_gib_usd_per_second
    )
    return {
        "evidence_kind": "estimate_not_cloud_measurement",
        "monthly_analyses": monthly_analyses,
        "proxy_inputs": {
            "mean_input_tokens_from_local_gemma": round(mean_input_tokens, 3),
            "mean_output_tokens_from_local_gemma": round(mean_output_tokens, 3),
            "local_mediapipe_wall_seconds": media_seconds,
            "local_mediapipe_peak_rss_mb": float(mediapipe["runs"][0]["peak_rss_mb"]),
        },
        "unit_prices_usd": {
            "gemini_3_5_flash_lite_input_per_million_tokens": input_usd_per_million,
            "gemini_3_5_flash_lite_output_including_thinking_per_million_tokens": output_usd_per_million,
            "cloud_run_cpu_per_vcpu_second": cpu_usd_per_second,
            "cloud_run_memory_per_gib_second": memory_gib_usd_per_second,
        },
        "scenario": {
            "assumed_vcpu": 1,
            "assumed_memory_gib": round(peak_gib, 6),
            "llm_usd_per_analysis": round(llm_per_analysis, 8),
            "compute_usd_per_analysis": round(compute_per_analysis, 8),
            "combined_usd_per_analysis": round(llm_per_analysis + compute_per_analysis, 8),
            "combined_usd_per_month": round(
                monthly_analyses * (llm_per_analysis + compute_per_analysis), 4
            ),
        },
        "excluded": [
            "storage, network egress, logging, database, retries and taxes",
            "Cloud Run free tier and committed-use discounts",
            "cloud cold-start and queue latency",
        ],
        "sources": {
            "pricing_checked_on": "2026-09-26",
            "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
            "cloud_run": "https://cloud.google.com/run/pricing",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mediapipe", type=Path, required=True)
    parser.add_argument("--gemma", type=Path, required=True)
    parser.add_argument("--monthly-analyses", type=int, default=10_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.monthly_analyses < 1:
        raise ValueError("monthly analyses must be positive")
    payload = calculate_estimate(
        json.loads(args.mediapipe.read_text()),
        json.loads(args.gemma.read_text()),
        args.monthly_analyses,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
