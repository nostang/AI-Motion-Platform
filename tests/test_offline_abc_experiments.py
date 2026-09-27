import importlib.util
import io
import json
import urllib.error
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
    assert "snake_case" in gemma._prompt(compact, "v3")
    assert "body_coordination" in gemma._prompt(compact, "v3")
    assert gemma._percentile([1.0, 2.0, 3.0], 0.5) == 2.0
    lean = gemma._lean_compact_report(
        {
            "score_breakdown": {
                "swing": {
                    "score": 18,
                    "max_score": 25,
                    "level": "GOOD",
                    "source_rule_id": "RULE-1",
                    "measurement_levels": {"speed": "GOOD"},
                }
            },
            "limitations": ["one", "two", "three", "four", "five"],
        }
    )
    assert lean["score_breakdown"] == {"swing": {"score": 18, "level": "GOOD"}}
    assert lean["limitations"] == ["one", "two", "three", "four"]
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


def test_gemma_schema_matches_five_field_contract():
    gemma = _load("benchmark_gemma4")

    assert set(gemma.OUTPUT_SCHEMA["required"]) == gemma.REQUIRED_KEYS
    assert gemma.OUTPUT_SCHEMA["additionalProperties"] is False
    assert gemma.OUTPUT_SCHEMA["properties"]["summary"]["type"] == "string"
    assert gemma.OUTPUT_SCHEMA["properties"]["strength"]["type"] == "array"
    assert gemma.OUTPUT_SCHEMA["properties"]["caution"]["type"] == "string"


def test_mp_yolo_sampling_uses_interior_timestamps():
    builder = _load("build_mp_yolo_hand_corpus")

    assert builder._interior_timestamps(1000, 2000, 4) == [1125, 1375, 1625, 1875]


def test_mp_yolo_pairs_racket_to_nearest_visible_wrist():
    benchmark = _load("benchmark_mp_yolo_hand")
    landmarks = {
        "left_shoulder": {"x": 40.0, "y": 50.0, "visibility": 1.0},
        "right_shoulder": {"x": 60.0, "y": 50.0, "visibility": 1.0},
        "left_wrist": {"x": 30.0, "y": 80.0, "visibility": 1.0},
        "right_wrist": {"x": 80.0, "y": 80.0, "visibility": 1.0},
    }
    boxes = [{"confidence": 0.9, "xyxy": [75.0, 70.0, 95.0, 95.0]}]

    paired = benchmark.pair_racket_to_wrist(boxes, landmarks)

    assert paired is not None
    assert paired["paired_side"] == "right"
    assert paired["right_distance_shoulder_widths"] == 0.0


def test_yolo_scale_summary_is_dashboard_ready_and_prefers_quality(tmp_path):
    summarizer = _load("summarize_yolo26_scale_runs")

    def payload(model_name, agreement, coverage, latency):
        return {
            "runtime": {"device": "mps", "image_size": 1280, "confidence_threshold": 0.15},
            "dataset": {"case_count": 1},
            "mediapipe_only": {"case_count": 1},
            "limitations": [],
            "models": [
                {
                    "model": model_name,
                    "weights_size_bytes": 10,
                    "weights_sha256": model_name,
                    "parameter_count": 10,
                    "fine_tuned_on_project_data": False,
                    "pose_valid_frame_count": 1,
                    "raw_detection_frame_count": 1,
                    "raw_detection_frame_rate": 1.0,
                    "paired_frame_count": 1,
                    "paired_frame_rate": 1.0,
                    "determined_case_count": 1,
                    "coverage_rate": coverage,
                    "right_hand_case_agreement_rate_all_cases": agreement,
                    "right_hand_case_agreement_rate_when_determined": agreement,
                    "model_load_wall_seconds": 0.1,
                    "warmup_wall_seconds": 0.2,
                    "latency": {
                        "mean_wall_seconds_per_frame": latency,
                        "p50_wall_seconds_per_frame": latency,
                        "p95_wall_seconds_per_frame": latency,
                    },
                    "process_peak_rss_mb_after_model": 100.0,
                    "process_peak_rss_delta_mb": 10.0,
                    "cases": [
                        {
                            "case_id": "CASE-1",
                            "human_racket_side": "right",
                            "decision": {"estimated": "right", "vote_counts": {"left": 0, "right": 1}},
                            "agreement": True,
                            "frames": [{"inference_wall_seconds": latency}],
                        }
                    ],
                }
            ],
        }

    paths = []
    for name, agreement, coverage, latency in (
        ("YOLO26n", 0.8, 1.0, 0.01),
        ("YOLO26s", 1.0, 0.9, 0.02),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload(name, agreement, coverage, latency)))
        paths.append(path)

    result = summarizer.summarize(paths)

    assert result["schema_version"] == "ai-motion-dashboard-experiment-v1"
    assert result["status"] == "completed"
    assert result["queue_assumption"]["concurrency"] == 1
    assert result["recommendation"]["model"] == "YOLO26s"
    assert result["models"][0]["local_single_worker_cost_proxy"]["money_cost_usd"] is None


def test_local_guardrails_normalize_types_and_use_safe_fallback(tmp_path):
    guardrails = _load("apply_local_llm_guardrails")
    normalized, changes = guardrails._normalize_response(
        {
            "summary": ["第一句", "第二句"],
            "strength": "優點",
            "priority": ["weight_transfer"],
            "drill": ["練習"],
            "caution": ["單鏡頭 2D 限制"],
            "extra": "remove me",
        }
    )
    assert normalized == {
        "summary": "第一句 第二句",
        "strength": ["優點"],
        "priority": ["weight_transfer"],
        "drill": ["練習"],
        "caution": "單鏡頭 2D 限制",
    }
    assert "summary:string_list_to_string" in changes
    assert "strength:string_to_string_list" in changes
    assert "removed_extra_keys:extra" in changes

    report = {
        "assessment_id": "CASE-GUARDRAIL",
        "assessment_type": "serve",
        "summary": {"evaluation_status": "EVALUATED", "overall_score": 70},
        "highlights": {
            "strengths": ["ready_position"],
            "improvement_priorities": ["weight_transfer"],
        },
        "limitations": ["single camera 2D"],
    }
    report_path = tmp_path / "analysis_report.json"
    report_path.write_text(json.dumps(report))
    fallback = guardrails._safe_fallback(
        {
            "case_id": "CASE-GUARDRAIL",
            "motion": "serve",
            "report_path": str(report_path),
            "input_overall_score": 70,
        },
        "minimal",
    )
    assert isinstance(fallback["summary"], str)
    assert "ready_position" in fallback["strength"][0]
    assert "weight_transfer" in fallback["priority"][0]
    assert "單攝影機 2D" in fallback["caution"]


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


def test_gemini_preflight_is_zero_network_and_cost_capped(tmp_path):
    gemini = _load("benchmark_gemini_corpus")
    assert gemini._request_payload("hello")["generationConfig"]["responseMimeType"] == "application/json"
    assert gemini._request_payload("hello")["generationConfig"]["responseJsonSchema"] == gemini.OUTPUT_SCHEMA
    assert set(gemini.OUTPUT_SCHEMA["required"]) == gemini.REQUIRED_KEYS

    cases = [
        {
            "case_id": "S-SV-01",
            "evidence_kind": "synthetic_structured_stress_case",
            "motion": "serve",
            "scenario": "smoke",
            "report_path": str(tmp_path / "report.json"),
            "prompt_sha256": "0" * 64,
            "estimated_input_tokens": 500,
        }
    ]
    plan = gemini._preflight(cases, gemini.DEFAULT_MODEL)
    assert plan["execution_evidence_kind"] == "cloud_api_dry_run_not_measurement"
    assert plan["data_boundary"].endswith("no video upload")
    assert plan["estimated_maximum_cost_usd"] < 0.01
    assert gemini._paid_tier_equivalent_cost_usd(500, 320) == 0.00095


def test_gemini_schema_and_usage_account_for_thinking_tokens():
    gemini = _load("benchmark_gemini_corpus")
    response = {
        "summary": "摘要",
        "strength": ["優點"],
        "priority": ["改善"],
        "drill": ["練習"],
        "caution": "單鏡頭2D限制",
    }
    assert gemini._schema_types_valid(response)
    assert not gemini._schema_types_valid({**response, "strength": "優點"})
    usage = gemini._usage(
        {
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 50,
                "thoughtsTokenCount": 25,
                "totalTokenCount": 175,
            }
        }
    )
    assert usage["billable_output_tokens"] == 75

    error = urllib.error.HTTPError(
        "https://example.invalid",
        400,
        "Bad Request",
        {},
        io.BytesIO(b'{"error":{"code":400,"message":"safe detail","status":"INVALID_ARGUMENT"}}'),
    )
    assert gemini._safe_error(error)["provider_error"]["message"] == "safe detail"


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
    assert evaluator._grounded_and_complete(
        ["改善重心轉移（weight_transfer）"], ["weight_transfer"]
    )
    assert not evaluator._grounded_and_complete(["憑空新增改善"], [])
    assert evaluator._grounded_and_complete(["無改善項目"], [])
    assert not evaluator._grounded_and_complete(
        ["改善重心轉移（weight_transfer）", "憑空新增項目"], ["weight_transfer"]
    )


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
    assert evaluated["checks"]["all_priorities_grounded"] is True

    assert evaluator._positive_metric_tokens(
        {"swing": {"level": "FAIR", "measurement_levels": {"path": "EXCELLENT"}}}
    ) == {"path"}


def test_llm_corpus_rejects_invented_priority_when_input_has_none(tmp_path):
    evaluator = _load("evaluate_llm_corpus")
    report = {
        "assessment_id": "CASE-NO-PRIORITY",
        "assessment_type": "serve",
        "summary": {"evaluation_status": "EVALUATED", "overall_score": 95},
        "highlights": {"strengths": ["tempo_stability"], "improvement_priorities": []},
        "limitations": ["single camera 2D"],
    }
    report_path = tmp_path / "analysis_report.json"
    report_path.write_text(json.dumps(report))
    case = {
        "case_id": "CASE-NO-PRIORITY",
        "report_path": str(report_path),
        "input_overall_score": 95,
        "response": {
            "summary": "摘要",
            "strength": ["節奏穩定（tempo_stability）"],
            "priority": ["憑空新增改善"],
            "drill": ["練習"],
            "caution": "單鏡頭2D限制",
        },
    }

    evaluated = evaluator._evaluate_case(case)
    assert evaluated["checks"]["all_priorities_grounded"] is False


def test_llm_corpus_accepts_empty_strength_when_evidence_is_insufficient(tmp_path):
    evaluator = _load("evaluate_llm_corpus")
    report = {
        "assessment_id": "CASE-EMPTY",
        "assessment_type": "clear",
        "summary": {"evaluation_status": "INSUFFICIENT_EVIDENCE", "overall_score": None},
        "highlights": {"strengths": [], "improvement_priorities": []},
        "limitations": ["single camera 2D"],
    }
    report_path = tmp_path / "analysis_report.json"
    report_path.write_text(json.dumps(report))
    case = {
        "case_id": "CASE-EMPTY",
        "report_path": str(report_path),
        "input_overall_score": None,
        "response": {
            "summary": "證據不足，無法評分",
            "strength": [],
            "priority": [],
            "drill": [],
            "caution": "單鏡頭2D限制",
        },
    }

    evaluated = evaluator._evaluate_case(case)
    assert evaluated["checks"]["strength_grounded_or_explicitly_none"] is True


def test_blind_ab_review_hides_provider_and_keeps_mapping():
    blind = _load("build_blind_ab_review")
    a_run = {"cases": [{"case_id": "CASE-1", "response": {"summary": "A"}}]}
    b_run = {"cases": [{"case_id": "CASE-1", "response": {"summary": "B"}}]}
    rows, mapping = blind.build_rows(a_run, b_run, seed=7)

    assert len(rows) == 2
    assert "system" not in rows[0]
    assert {item["system"] for item in mapping} == {"A", "B"}
    assert {item["blind_output_id"] for item in mapping} == {
        row["blind_output_id"] for row in rows
    }
