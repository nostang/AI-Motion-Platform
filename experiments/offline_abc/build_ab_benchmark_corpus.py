#!/usr/bin/env python3
"""Build an auditable real/synthetic report corpus for the A-vs-B comparison."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import platform
import re
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.clear_demo import run_clear_demo  # noqa: E402
from src.pose_demo import run_pose_demo  # noqa: E402
from src.serve_demo import run_serve_demo  # noqa: E402


VIDEO_SUFFIXES = {".mov", ".mp4", ".m4v"}
MOTION_ORDER = {"clear": 0, "footwork": 1, "serve": 2}
MOTION_CODE = {"clear": "CLR", "footwork": "FW", "serve": "SV"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def _video_metadata(path: Path) -> dict[str, float | int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"OpenCV cannot open {path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        return {
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
            "fps": round(fps, 3),
            "frames": frames,
            "duration_seconds": round(frames / fps, 3) if fps else 0.0,
            "size_bytes": path.stat().st_size,
        }
    finally:
        capture.release()


def _find_source(directory: Path) -> Path | None:
    for name in ("source.mov", "source.mp4", "source.m4v"):
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def _discover_real_cases(root: Path) -> list[dict[str, Any]]:
    """Return one deterministic case per unique video hash and motion label."""

    grouped: dict[tuple[str, str], dict[str, list[Any]]] = defaultdict(
        lambda: {"paths": [], "annotations": []}
    )

    dataset_root = root / "dataset"
    for motion in MOTION_ORDER:
        video_dir = dataset_root / motion / "videos"
        if not video_dir.exists():
            continue
        for path in sorted(video_dir.iterdir(), key=lambda item: item.name.lower()):
            if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES:
                grouped[(_sha256(path), motion)]["paths"].append(path)

    assessment_root = root / "api_data" / "motion_assessments"
    for annotation_path in sorted(assessment_root.glob("*/human_annotation.json")):
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        motion = str(annotation.get("motion_type") or "")
        if motion not in MOTION_ORDER:
            continue
        source = _find_source(annotation_path.parent)
        if source is None:
            continue
        key = (_sha256(source), motion)
        grouped[key]["paths"].append(source)
        grouped[key]["annotations"].append(
            {
                "path": annotation_path,
                "updated_at": str(annotation.get("updated_at") or ""),
                "window": annotation.get("window") or {},
                "racket_side": annotation.get("racket_side"),
            }
        )

    numbered: dict[str, int] = defaultdict(int)
    cases = []
    for (video_hash, motion), group in sorted(
        grouped.items(),
        key=lambda item: (
            MOTION_ORDER[item[0][1]],
            min(_relative(path, root).lower() for path in item[1]["paths"]),
            item[0][0],
        ),
    ):
        paths = sorted(
            set(group["paths"]),
            key=lambda path: (
                0 if "dataset" in path.parts else 1,
                _relative(path, root).lower(),
            ),
        )
        annotations = sorted(
            group["annotations"],
            key=lambda item: (item["updated_at"], str(item["path"])),
            reverse=True,
        )
        selected_annotation = annotations[0] if annotations else None
        numbered[motion] += 1
        case_id = f"R-{MOTION_CODE[motion]}-{numbered[motion]:02d}"
        window = (selected_annotation or {}).get("window") or {}
        cases.append(
            {
                "case_id": case_id,
                "evidence_kind": "real_video_pipeline_output",
                "motion": motion,
                "video_sha256": video_hash,
                "video_path": _relative(paths[0], root),
                "source_aliases": [_relative(path, root) for path in paths],
                "annotation_count": len(annotations),
                "selected_annotation": (
                    _relative(selected_annotation["path"], root)
                    if selected_annotation
                    else None
                ),
                "window": {
                    "start_ms": window.get("start_ms"),
                    "end_ms": window.get("end_ms"),
                    "source": window.get("source"),
                },
                "racket_side": (selected_annotation or {}).get("racket_side"),
                "status": "pending",
            }
        )
    return cases


def _synthetic_cases() -> list[dict[str, Any]]:
    """Return deterministic structured reports; none of these came from a video."""

    specifications = [
        ("S-CLR-01", "clear", 92, 0.97, ["擊球準備穩定"], ["收拍完整性"], "high_score_minor_issue"),
        ("S-CLR-02", "clear", 48, 0.91, ["重心仍可辨識"], ["引拍高度", "身體旋轉"], "low_score_multiple_priorities"),
        ("S-CLR-03", "clear", None, 0.22, [], [], "insufficient_evidence_no_score"),
        ("S-FW-01", "footwork", 88, 0.95, ["回位節奏穩定"], ["啟動反應"], "high_score_single_priority"),
        ("S-FW-02", "footwork", 35, 0.89, ["能完成移動"], ["回中心位置", "左右平衡"], "low_score_multiple_priorities"),
        ("S-FW-03", "footwork", 67, 0.41, ["部分步序可辨識"], ["步幅一致性"], "low_confidence_scored"),
        ("S-SV-01", "serve", 95, 0.99, ["動作節奏穩定"], [], "high_score_no_priority"),
        ("S-SV-02", "serve", 52, 0.94, ["準備姿勢可辨識"], ["擊球點穩定度", "重心轉移"], "low_score_multiple_priorities"),
        ("S-SV-03", "serve", 73, 0.63, ["出手方向一致"], ["手腕控制"], "medium_confidence_forbidden_visual_claim_trap"),
    ]
    cases = []
    for case_id, motion, score, confidence, strengths, priorities, scenario in specifications:
        evaluated = score is not None
        report = {
            "assessment_id": case_id,
            "assessment_type": motion,
            "summary": {
                "completed": evaluated,
                "evaluation_status": "EVALUATED" if evaluated else "INSUFFICIENT_EVIDENCE",
                "overall_score": score,
                "system_confidence": confidence,
            },
            "score_breakdown": {
                "stability": score,
                "coordination": None if score is None else max(0, score - 7),
            },
            "highlights": {
                "strengths": strengths,
                "improvement_priorities": priorities,
            },
            "limitations": [
                "單鏡頭 2D 姿態資料，未直接偵測羽球或球拍",
                "此案例是結構化壓力測試，不是影片分析結果",
            ],
            "benchmark_metadata": {
                "evidence_kind": "synthetic_structured_stress_case",
                "not_from_video": True,
                "scenario": scenario,
                "must_not_be_counted_as_real_subject": True,
            },
        }
        cases.append(
            {
                "case_id": case_id,
                "evidence_kind": "synthetic_structured_stress_case",
                "motion": motion,
                "scenario": scenario,
                "report": report,
                "status": "generated",
            }
        )
    return cases


def _run_real_case(case: dict[str, Any], root: Path, model: Path, temp_dir: Path) -> dict:
    video_path = root / case["video_path"]
    window = case["window"]
    kwargs = {
        "video_path": video_path,
        "model_path": model,
        "display": False,
        "output_dir": temp_dir,
        "start_ms": window.get("start_ms"),
        "end_ms": window.get("end_ms"),
    }
    started = time.perf_counter()
    console = io.StringIO()
    with contextlib.redirect_stdout(console):
        if case["motion"] == "clear":
            result = run_clear_demo(
                video_id=case["case_id"],
                **kwargs,
            )
        elif case["motion"] == "serve":
            result = run_serve_demo(
                video_id=case["case_id"],
                racket_side=case.get("racket_side"),
                **kwargs,
            )
        else:
            result = run_pose_demo(**kwargs)
    report = result.get("analysis_report") or result.get("report")
    if not isinstance(report, dict):
        raise RuntimeError("Pipeline did not return an analysis report")
    return {
        "report": report,
        "wall_seconds": round(time.perf_counter() - started, 4),
        "video": _video_metadata(video_path),
        "console_tail": console.getvalue().splitlines()[-8:],
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _manifest_payload(real_cases: list[dict[str, Any]], synthetic_cases: list[dict[str, Any]]) -> dict:
    real_success = sum(case["status"] == "completed" for case in real_cases)
    real_failed = sum(case["status"] == "failed" for case in real_cases)
    return {
        "corpus": "a-vs-b-motion-report-corpus",
        "schema_version": "1.0",
        "evidence_policy": {
            "real": "Generated by the existing local MediaPipe/rule pipeline from a unique video-motion pair.",
            "synthetic": "Generated structured JSON for LLM stress testing; never count as a real video or subject.",
        },
        "runtime": {"platform": platform.platform(), "python": platform.python_version()},
        "summary": {
            "real_discovered": len(real_cases),
            "real_completed": real_success,
            "real_failed": real_failed,
            "real_pending": len(real_cases) - real_success - real_failed,
            "synthetic_generated": len(synthetic_cases),
            "usable_report_count": real_success + len(synthetic_cases),
        },
        "real_cases": real_cases,
        "synthetic_cases": [
            {key: value for key, value in case.items() if key != "report"}
            for case in synthetic_cases
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--model",
        type=Path,
        default=PROJECT_ROOT / "models" / "pose_landmarker_lite.task",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=PROJECT_ROOT / "experiments" / "offline_abc" / "corpus",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "experiments" / "offline_abc" / "results" / "ab_corpus_manifest.json",
    )
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    real_cases = _discover_real_cases(args.root)
    synthetic_cases = _synthetic_cases()

    for case in synthetic_cases:
        report_path = args.corpus_dir / "synthetic" / case["case_id"] / "analysis_report.json"
        _write_json(report_path, case["report"])
        case["report_path"] = _relative(report_path, args.root)

    _write_json(args.manifest, _manifest_payload(real_cases, synthetic_cases))
    if args.inventory_only:
        print(json.dumps(_manifest_payload(real_cases, synthetic_cases), ensure_ascii=False, indent=2))
        return

    for index, case in enumerate(real_cases, start=1):
        report_path = args.corpus_dir / "real" / case["case_id"] / "analysis_report.json"
        if report_path.exists() and not args.force:
            case["status"] = "completed"
            case["report_path"] = _relative(report_path, args.root)
            case["reused_existing_report"] = True
        else:
            try:
                with tempfile.TemporaryDirectory(prefix=f"ab-corpus-{case['case_id']}-") as temp:
                    output = _run_real_case(case, args.root, args.model, Path(temp))
                _write_json(report_path, output.pop("report"))
                case.update(output)
                case["status"] = "completed"
                case["report_path"] = _relative(report_path, args.root)
                case["reused_existing_report"] = False
            except Exception as error:  # noqa: BLE001 - failures are corpus evidence
                case["status"] = "failed"
                case["error_type"] = type(error).__name__
                case["error"] = re.sub(r"/Users/[^/]+/", "/Users/<redacted>/", str(error))
        _write_json(args.manifest, _manifest_payload(real_cases, synthetic_cases))
        print(f"[{index:02d}/{len(real_cases):02d}] {case['case_id']} {case['motion']}: {case['status']}")

    print(json.dumps(_manifest_payload(real_cases, synthetic_cases)["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
