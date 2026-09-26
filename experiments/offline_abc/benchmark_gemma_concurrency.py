#!/usr/bin/env python3
"""Measure local Ollama/Gemma behavior when requests arrive together."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from benchmark_gemma4 import _call_ollama, _compact_report, _ollama_process, _prompt, _validate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", default="gemma4:e2b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/api/generate")
    parser.add_argument("--concurrency", type=int, action="append", default=[])
    parser.add_argument("--batches", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    levels = args.concurrency or [1, 2]
    if any(level < 1 for level in levels) or args.batches < 1:
        raise ValueError("concurrency levels and batches must be positive")

    compact = _compact_report(json.loads(args.report.read_text()))
    prompt = _prompt(compact)
    _call_ollama(args.endpoint, args.model, prompt)  # warm the model before comparison

    results = []
    for concurrency in levels:
        batches = []
        for batch_number in range(1, args.batches + 1):
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                raw_cases = list(
                    executor.map(
                        lambda _: _call_ollama(args.endpoint, args.model, prompt),
                        range(concurrency),
                    )
                )
            batch_seconds = time.perf_counter() - started
            cases = []
            for raw in raw_cases:
                response = raw.get("response", "")
                eval_duration = int(raw.get("eval_duration") or 0)
                eval_count = int(raw.get("eval_count") or 0)
                cases.append(
                    {
                        "wall_seconds": round(raw["client_wall_seconds"], 4),
                        "tokens_per_second": round(eval_count / (eval_duration / 1e9), 3) if eval_duration else None,
                        "success": all(
                            _validate(response, compact)[key]
                            for key in ("json_valid", "required_keys", "caution_present")
                        ),
                    }
                )
            batches.append(
                {
                    "batch": batch_number,
                    "batch_wall_seconds": round(batch_seconds, 4),
                    "requests_per_second": round(concurrency / batch_seconds, 4),
                    "cases": cases,
                }
            )
        latencies = [case["wall_seconds"] for batch in batches for case in batch["cases"]]
        throughputs = [batch["requests_per_second"] for batch in batches]
        results.append(
            {
                "concurrency": concurrency,
                "batches": batches,
                "aggregate": {
                    "request_count": len(latencies),
                    "mean_request_wall_seconds": round(statistics.fmean(latencies), 4),
                    "mean_requests_per_second": round(statistics.fmean(throughputs), 4),
                    "success_rate": round(
                        sum(case["success"] for batch in batches for case in batch["cases"])
                        / len(latencies),
                        3,
                    ),
                },
            }
        )

    payload = {
        "benchmark": "local-gemma4-concurrency",
        "model": args.model,
        "warmup_excluded": True,
        "report": str(args.report),
        "resource": _ollama_process(args.endpoint, args.model),
        "levels": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
