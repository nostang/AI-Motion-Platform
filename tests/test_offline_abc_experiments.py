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
