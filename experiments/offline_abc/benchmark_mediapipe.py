#!/usr/bin/env python3
"""Benchmark the existing MediaPipe motion pipeline without cloud services."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import statistics
import sys
import tempfile
import time
from pathlib import Path

import cv2


MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from src.clear_demo import run_clear_demo  # noqa: E402
from src.pose_demo import run_pose_demo  # noqa: E402
from src.serve_demo import run_serve_demo  # noqa: E402


def _video_metadata(path: Path) -> dict[str, float | int | str]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV cannot open {path}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        return {
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            "fps": round(fps, 3),
            "frames": frames,
            "duration_seconds": round(frames / fps, 3) if fps else 0.0,
            "size_bytes": path.stat().st_size,
        }
    finally:
        cap.release()


def _run_once(
    motion: str,
    case_id: str,
    video: Path,
    model: Path,
    output_dir: Path,
) -> dict:
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    if motion == "clear":
        result = run_clear_demo(
            video_id=case_id,
            video_path=video,
            model_path=model,
            display=False,
            output_dir=output_dir,
        )
    elif motion == "serve":
        result = run_serve_demo(
            video_id=case_id,
            video_path=video,
            model_path=model,
            display=False,
            output_dir=output_dir,
        )
    elif motion == "footwork":
        result = run_pose_demo(
            video_path=video,
            model_path=model,
            display=False,
            output_dir=output_dir,
        )
    else:
        raise ValueError(f"Unsupported motion: {motion}")

    report = result.get("analysis_report") or result.get("report") or {}
    summary = report.get("summary") or {}
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = max_rss / (1024 * 1024) if sys.platform == "darwin" else max_rss / 1024
    return {
        "wall_seconds": round(time.perf_counter() - started_wall, 4),
        "cpu_seconds": round(time.process_time() - started_cpu, 4),
        "peak_rss_mb": round(peak_rss_mb, 2),
        "evaluation_status": summary.get("evaluation_status"),
        "overall_score": summary.get("overall_score"),
        "system_confidence": summary.get("system_confidence"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--motion", choices=("clear", "serve", "footwork"), required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument(
        "--model",
        type=Path,
        default=MODULE_ROOT / "models" / "pose_landmarker_lite.task",
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.repeats < 1:
        raise ValueError("--repeats must be at least 1")

    metadata = _video_metadata(args.video)
    runs = []
    with tempfile.TemporaryDirectory(prefix="bpo-mediapipe-") as temp_root:
        for index in range(args.repeats):
            runs.append(
                _run_once(
                    args.motion,
                    args.case_id,
                    args.video,
                    args.model,
                    Path(temp_root) / f"run-{index + 1}",
                )
            )

    mean_wall = statistics.fmean(run["wall_seconds"] for run in runs)
    payload = {
        "benchmark": "local-mediapipe-existing-pipeline",
        "case_id": args.case_id,
        "motion": args.motion,
        "video": metadata,
        "runtime": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "opencv": cv2.__version__,
            "model_file": args.model.name,
        },
        "runs": runs,
        "aggregate": {
            "repeat_count": len(runs),
            "mean_wall_seconds": round(mean_wall, 4),
            "mean_realtime_factor": round(mean_wall / metadata["duration_seconds"], 4),
            "mean_processed_fps": round(metadata["frames"] / mean_wall, 3),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
