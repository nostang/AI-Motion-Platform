#!/usr/bin/env python3
"""Aggregate repeated YOLO26 n/s/m runs into a dashboard-ready comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def _model_summary(model_name: str, runs: list[tuple[Path, dict[str, Any]]]) -> dict[str, Any]:
    model_payloads = [payload["models"][0] for _, payload in runs]
    first = model_payloads[0]
    inference_seconds = [
        frame["inference_wall_seconds"]
        for model in model_payloads
        for case in model["cases"]
        for frame in case["frames"]
        if "inference_wall_seconds" in frame
    ]
    quality_keys = (
        "pose_valid_frame_count",
        "raw_detection_frame_count",
        "raw_detection_frame_rate",
        "paired_frame_count",
        "paired_frame_rate",
        "determined_case_count",
        "coverage_rate",
        "right_hand_case_agreement_rate_all_cases",
        "right_hand_case_agreement_rate_when_determined",
    )
    quality_consistent = all(
        all(model[key] == first[key] for key in quality_keys)
        for model in model_payloads[1:]
    )
    mean_seconds = statistics.fmean(inference_seconds)
    p50_seconds = statistics.median(inference_seconds)
    p95_seconds = _percentile(inference_seconds, 0.95)
    run_summaries = []
    for path, payload in runs:
        model = payload["models"][0]
        run_summaries.append(
            {
                "source_path": str(path),
                "source_sha256": _sha256(path),
                "model_load_wall_seconds": model["model_load_wall_seconds"],
                "warmup_wall_seconds": model["warmup_wall_seconds"],
                "mean_wall_seconds_per_frame": model["latency"]["mean_wall_seconds_per_frame"],
                "p50_wall_seconds_per_frame": model["latency"]["p50_wall_seconds_per_frame"],
                "p95_wall_seconds_per_frame": model["latency"]["p95_wall_seconds_per_frame"],
                "process_peak_rss_mb_after_model": model["process_peak_rss_mb_after_model"],
                "process_peak_rss_delta_mb": model["process_peak_rss_delta_mb"],
            }
        )
    return {
        "model": model_name,
        "model_scale": model_name[-1].lower(),
        "run_count": len(runs),
        "quality_consistent_across_runs": quality_consistent,
        "weights_size_bytes": first["weights_size_bytes"],
        "weights_sha256": first["weights_sha256"],
        "parameter_count": first["parameter_count"],
        "fine_tuned_on_project_data": first["fine_tuned_on_project_data"],
        "quality": {key: first[key] for key in quality_keys},
        "latency_across_all_measured_frames": {
            "measured_frame_count": len(inference_seconds),
            "mean_wall_seconds_per_frame": round(mean_seconds, 6),
            "p50_wall_seconds_per_frame": round(p50_seconds, 6),
            "p95_wall_seconds_per_frame": round(p95_seconds, 6),
            "mean_frames_per_second": round(1 / mean_seconds, 3),
        },
        "local_single_worker_cost_proxy": {
            "estimated_seconds_per_video_at_12_frames": round(mean_seconds * 12, 6),
            "estimated_compute_minutes_per_10000_videos": round(mean_seconds * 120000 / 60, 3),
            "money_cost_usd": None,
            "money_cost_note": "Local M5 Pro elapsed-time proxy only; power draw was not measured and no paid API or VM was used.",
        },
        "resource_across_runs": {
            "median_model_load_wall_seconds": round(
                statistics.median(item["model_load_wall_seconds"] for item in run_summaries), 6
            ),
            "median_warmup_wall_seconds": round(
                statistics.median(item["warmup_wall_seconds"] for item in run_summaries), 6
            ),
            "median_process_peak_rss_mb_after_model": round(
                statistics.median(item["process_peak_rss_mb_after_model"] for item in run_summaries), 2
            ),
            "median_process_peak_rss_delta_mb": round(
                statistics.median(item["process_peak_rss_delta_mb"] for item in run_summaries), 2
            ),
            "rss_note": "Process peak RSS is a local process-level measurement, not dedicated GPU memory.",
        },
        "cases": [
            {
                "case_id": case["case_id"],
                "human_racket_side": case["human_racket_side"],
                "estimated": case["decision"]["estimated"],
                "vote_counts": case["decision"]["vote_counts"],
                "agreement": case["agreement"],
            }
            for case in first["cases"]
        ],
        "runs": run_summaries,
    }


def summarize(run_paths: list[Path]) -> dict[str, Any]:
    grouped: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    payloads = []
    for path in run_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if len(payload.get("models") or []) != 1:
            raise ValueError(f"each repeated run must contain exactly one model: {path}")
        grouped[payload["models"][0]["model"]].append((path, payload))
        payloads.append(payload)
    if not payloads:
        raise ValueError("at least one run is required")
    comparison_fields = ("device", "image_size", "confidence_threshold")
    first_runtime = payloads[0]["runtime"]
    if any(
        any(payload["runtime"][field] != first_runtime[field] for field in comparison_fields)
        for payload in payloads[1:]
    ):
        raise ValueError("runs do not share the same device, image size, and confidence threshold")
    scale_order = {"YOLO26n": 0, "YOLO26s": 1, "YOLO26m": 2}
    models = [
        _model_summary(name, runs)
        for name, runs in sorted(grouped.items(), key=lambda item: scale_order.get(item[0], 99))
    ]
    recommended = max(
        models,
        key=lambda model: (
            model["quality"]["right_hand_case_agreement_rate_all_cases"],
            model["quality"]["coverage_rate"],
            -model["latency_across_all_measured_frames"]["p95_wall_seconds_per_frame"],
        ),
    )
    return {
        "schema_version": "ai-motion-dashboard-experiment-v1",
        "experiment": "yolo26-n-s-m-local-single-worker-comparison",
        "status": "completed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "claim_scope": "right-hand-only-pretrained-racket-proxy-screening_not_balanced_accuracy_or_map",
        "runtime": first_runtime,
        "dataset": payloads[0]["dataset"],
        "mediapipe_only": payloads[0]["mediapipe_only"],
        "queue_assumption": {
            "worker_count": 1,
            "concurrency": 1,
            "paid_cloud_resources": False,
            "note": "Single-user local MVP; sequential elapsed-time proxy, not a production capacity claim.",
        },
        "models": models,
        "recommendation": {
            "model": recommended["model"],
            "rule": "highest right-hand case agreement, then coverage, then lowest aggregated p95 latency",
            "production_ready": False,
            "next_gate": "add left-hand cases, mirror metadata, and human racket boxes before fine-tuning or mAP claims",
        },
        "limitations": payloads[0]["limitations"]
        + [
            "All monetary inference costs are zero in this local experiment; electricity was not measured.",
            "The same six right-hand videos are repeated for timing stability, not counted as new participants.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"models": result["models"], "recommendation": result["recommendation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
