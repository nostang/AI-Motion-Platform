import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "experiments" / "offline_abc" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_gemma_validation_and_case_id(tmp_path):
    gemma = _load("benchmark_gemma4")
    compact = {"improvement_priorities": ["body_coordination"]}
    response = json.dumps(
        {
            "summary": "摘要",
            "strength": "穩定",
            "priority": ["body_coordination"],
            "drill": "練習",
            "caution": "單鏡頭限制",
        },
        ensure_ascii=False,
    )
    assert all(gemma._validate(response, compact).values())
    report = {"video_id": "SV_003", "assessment_id": "ignored"}
    assert gemma._case_id(tmp_path / "report.json", report) == "SV_003"
    assert gemma._parse_response("not json") is None
    assert "無明確優點" in gemma._prompt(compact, "v2")
    assert "無明確優點" not in gemma._prompt(compact, "v1")
    assert gemma._percentile([1.0, 2.0, 3.0], 0.5) == 2.0
    aggregate = gemma._aggregate_cases(
        [
            {
                "client_wall_seconds": 1.0,
                "tokens_per_second": 10.0,
                "success": True,
                "checks": {"json_valid": True, "required_keys": True, "priority_grounded": True},
            },
            {
                "client_wall_seconds": 3.0,
                "tokens_per_second": 20.0,
                "success": False,
                "checks": {"json_valid": True, "required_keys": False, "priority_grounded": False},
            },
        ]
    )
    assert aggregate["p50_wall_seconds"] == 2.0
    assert aggregate["success_rate"] == 0.5


def test_yolov12_tiny_dataset_is_single_class(tmp_path):
    yolo = _load("benchmark_yolov12")
    yaml_path = yolo._make_dataset(tmp_path, train_count=3, val_count=2, image_size=96)
    assert len(list((tmp_path / "images" / "train").glob("*.jpg"))) == 3
    assert len(list((tmp_path / "images" / "val").glob("*.jpg"))) == 2
    labels = list((tmp_path / "labels").glob("**/*.txt"))
    assert len(labels) == 5
    assert all(label.read_text().startswith("0 ") for label in labels)
    assert "0: synthetic_target" in yaml_path.read_text()


def test_yolov12_rejects_non_official_remote(tmp_path, monkeypatch):
    yolo = _load("benchmark_yolov12")
    monkeypatch.setattr(yolo, "_git", lambda *_args: "https://example.com/not-official.git")
    try:
        yolo._verify_official_repo(tmp_path)
    except RuntimeError as error:
        assert "non-official" in str(error)
    else:
        raise AssertionError("non-official source must be rejected")


def test_option_a_estimate_is_explicitly_not_a_measurement():
    estimate = _load("estimate_option_a")
    mediapipe = {
        "aggregate": {"mean_wall_seconds": 5.0},
        "runs": [{"peak_rss_mb": 512.0}],
    }
    gemma = {
        "cases": [
            {"prompt_tokens": 400, "output_tokens": 200},
            {"prompt_tokens": 600, "output_tokens": 100},
        ]
    }
    result = estimate.calculate_estimate(mediapipe, gemma, 10_000)
    assert result["evidence_kind"] == "estimate_not_cloud_measurement"
    assert result["proxy_inputs"]["mean_input_tokens_from_local_gemma"] == 500
    assert result["scenario"]["combined_usd_per_month"] > 0


def test_ab_corpus_has_separate_real_and_synthetic_evidence(tmp_path):
    corpus = _load("build_ab_benchmark_corpus")
    clear_video = tmp_path / "dataset" / "clear" / "videos" / "CL_001.mov"
    serve_video = tmp_path / "dataset" / "serve" / "videos" / "SV_001.mov"
    clear_video.parent.mkdir(parents=True)
    serve_video.parent.mkdir(parents=True)
    clear_video.write_bytes(b"clear-video")
    serve_video.write_bytes(b"serve-video")
    assessment = tmp_path / "api_data" / "motion_assessments" / "ma_1"
    assessment.mkdir(parents=True)
    (assessment / "source.mov").write_bytes(b"footwork-video")
    (assessment / "human_annotation.json").write_text(
        json.dumps(
            {
                "motion_type": "footwork",
                "window": {"start_ms": 100, "end_ms": 900, "source": "HUMAN"},
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )
    )

    real = corpus._discover_real_cases(tmp_path)
    synthetic = corpus._synthetic_cases()

    assert len(real) == 3
    assert len({(case["video_sha256"], case["motion"]) for case in real}) == 3
    assert {case["motion"] for case in real} == {"clear", "footwork", "serve"}
    assert len(synthetic) == 9
    assert all(case["report"]["benchmark_metadata"]["not_from_video"] for case in synthetic)
    assert all(
        case["report"]["benchmark_metadata"]["must_not_be_counted_as_real_subject"]
        for case in synthetic
    )


def test_ab_corpus_calls_clear_without_unsupported_racket_side(tmp_path, monkeypatch):
    corpus = _load("build_ab_benchmark_corpus")
    video = tmp_path / "source.mov"
    video.write_bytes(b"placeholder")
    captured = {}

    def fake_clear(**kwargs):
        captured.update(kwargs)
        return {"analysis_report": {"summary": {"overall_score": 80}}}

    monkeypatch.setattr(corpus, "run_clear_demo", fake_clear)
    monkeypatch.setattr(corpus, "_video_metadata", lambda _path: {"frames": 1})
    case = {
        "case_id": "R-CLR-01",
        "motion": "clear",
        "video_path": str(video.relative_to(tmp_path)),
        "window": {"start_ms": 0, "end_ms": 1000},
        "racket_side": "right",
    }
    result = corpus._run_real_case(case, tmp_path, tmp_path / "model.task", tmp_path / "out")

    assert "racket_side" not in captured
    assert result["report"]["summary"]["overall_score"] == 80


def test_llm_corpus_score_integrity():
    evaluator = _load("evaluate_llm_corpus")

    assert evaluator._score_integrity("整體評分為85分", 85) == (True, [85.0])
    assert evaluator._score_integrity("整體評分為90分", 85) == (False, [90.0])
    assert evaluator._score_integrity("沒有引用分數", 85) == (True, [])
    assert evaluator._score_integrity("缺乏足夠證據", None) == (True, [])


def test_llm_corpus_rejects_invented_strength_when_input_has_none(tmp_path):
    evaluator = _load("evaluate_llm_corpus")
    report = {
        "assessment_id": "CASE-1",
        "assessment_type": "clear",
        "summary": {"evaluation_status": "EVALUATED", "overall_score": 58},
        "highlights": {"strengths": [], "improvement_priorities": ["weight_transfer"]},
        "limitations": ["single camera 2D"],
    }
    report_path = tmp_path / "analysis_report.json"
    report_path.write_text(json.dumps(report))
    case = {
        "case_id": "CASE-1",
        "report_path": str(report_path),
        "input_overall_score": 58,
        "response": {
            "summary": "摘要",
            "strength": ["weight_transfer"],
            "priority": ["weight_transfer"],
            "drill": ["練習"],
            "caution": "單鏡頭2D限制",
        },
    }

    evaluated = evaluator._evaluate_case(case)
    assert evaluated["checks"]["strength_grounded_or_explicitly_none"] is False

    assert evaluator._positive_metric_tokens(
        {"swing": {"level": "FAIR", "measurement_levels": {"path": "EXCELLENT"}}}
    ) == {"path"}
