"""AI Motion 專案設定。"""

from pathlib import Path

from src.calibration_settings import load_footwork_calibration


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VIDEO_ID = "FW_001"

MODEL_PATH = PROJECT_ROOT / "models" / "pose_landmarker_lite.task"
WINDOW_NAME = "AI Motion - Footwork Pose Demo"
TRAJECTORY_MAX_POINTS = 90

CALIBRATION_CONFIG_PATH = (
    Path(__file__).resolve().parent
    / "config_data"
    / "footwork_calibration.json"
)
CALIBRATION_SETTINGS = load_footwork_calibration(CALIBRATION_CONFIG_PATH)
CALIBRATION_CONFIG_VERSION = CALIBRATION_SETTINGS.config_version
CALIBRATION_CONFIG_SNAPSHOT = CALIBRATION_SETTINGS.raw
MOTION_FEATURE_CALIBRATION_ENGINE = (
    CALIBRATION_SETTINGS.create_feature_calibration_engine()
)
MOTION_FEATURE_CALIBRATION_VERSION = (
    MOTION_FEATURE_CALIBRATION_ENGINE.config_version
)

CENTER_CALIBRATION_SECONDS = float(
    CALIBRATION_SETTINGS.center["calibration_seconds"]
)
CENTER_REGION_RADIUS = float(
    CALIBRATION_SETTINGS.center["region_radius"]
)

FOOTWORK_MOVE_OFFSET_THRESHOLD = float(
    CALIBRATION_SETTINGS.event["move_offset_threshold"]
)
FOOTWORK_RETURN_OFFSET_THRESHOLD = float(
    CALIBRATION_SETTINGS.event["return_offset_threshold"]
)
FOOTWORK_SMOOTHING_WINDOW = int(
    CALIBRATION_SETTINGS.event["smoothing_window"]
)
FOOTWORK_REVERSAL_CONFIRM_FRAMES = int(
    CALIBRATION_SETTINGS.event["reversal_confirm_frames"]
)
FOOTWORK_REVERSAL_MIN_DROP = float(
    CALIBRATION_SETTINGS.event["reversal_min_drop"]
)
FOOTWORK_READY_CONFIRM_FRAMES = int(
    CALIBRATION_SETTINGS.event["ready_confirm_frames"]
)
EXPECTED_FOOTWORK_EVENT_COUNT = int(
    CALIBRATION_SETTINGS.event["expected_event_count"]
)

DIRECTION_MIRROR_X = bool(CALIBRATION_SETTINGS.direction["mirror_x"])
DIRECTION_X_SCALE = float(CALIBRATION_SETTINGS.direction["x_scale"])
DIRECTION_Y_SCALE = float(CALIBRATION_SETTINGS.direction["y_scale"])
DIRECTION_MIN_VECTOR_LENGTH = float(
    CALIBRATION_SETTINGS.direction["min_vector_length"]
)
DIRECTION_MIN_CONFIDENCE = float(
    CALIBRATION_SETTINGS.direction["min_confidence"]
)

REVIEW_CLIP_PRE_ROLL_MS = int(
    CALIBRATION_SETTINGS.review["clip_pre_roll_ms"]
)
REVIEW_CLIP_POST_ROLL_MS = int(
    CALIBRATION_SETTINGS.review["clip_post_roll_ms"]
)
REVIEW_MINIMUM_REVIEWERS = int(
    CALIBRATION_SETTINGS.review["minimum_reviewers_for_consensus"]
)
REVIEW_CONSENSUS_VOTES_REQUIRED = int(
    CALIBRATION_SETTINGS.review["consensus_votes_required"]
)

ASSESSMENT_OUTPUT_PATH = PROJECT_ROOT / "output" / "footwork_assessment.json"
REVIEW_PACKAGE_OUTPUT_PATH = (
    PROJECT_ROOT / "output" / "footwork_review_package.json"
)
COACH_EVALUATION_OUTPUT_PATH = (
    PROJECT_ROOT / "output" / "coach_evaluation.json"
)
ANALYSIS_REPORT_OUTPUT_PATH = (
    PROJECT_ROOT / "output" / "footwork_analysis_report.json"
)
PIPELINE_VALIDATION_OUTPUT_PATH = (
    PROJECT_ROOT / "output" / "pipeline_validation.json"
)
