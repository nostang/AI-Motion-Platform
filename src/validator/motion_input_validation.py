"""Pre-scoring validation for reusable MediaPipe Pose observations.

The validator consumes landmarks inside the existing motion Pose loop. It does
not classify badminton motions and does not run MediaPipe itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import ceil, hypot, isfinite
from pathlib import Path
from statistics import fmean
from typing import Any, Mapping, Sequence


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "config_data"
    / "motion_input_validation_v1.json"
)

LANDMARK_INDEX = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}

UPPER_BODY = (
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
)
LOWER_BODY = (
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)
BODY_ANCHORS = tuple(LANDMARK_INDEX)

USER_MESSAGES = {
    "READY": "影片符合分析基本條件。",
    "NEEDS_REVIEW": "目前沒有偵測到足夠明顯的可分析動作，請確認影片內容。",
    "INVALID": "未偵測到可分析的人體動作，請重新錄製或上傳。",
}


def load_motion_input_validation_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _confidence(landmark: Any) -> float:
    visibility = float(getattr(landmark, "visibility", 1.0))
    presence = float(getattr(landmark, "presence", 1.0))
    return min(visibility, presence)


def _point(landmark: Any) -> tuple[float, float] | None:
    x = float(getattr(landmark, "x", float("nan")))
    y = float(getattr(landmark, "y", float("nan")))
    if not isfinite(x) or not isfinite(y):
        return None
    return x, y


def _distance(
    left: tuple[float, float],
    right: tuple[float, float],
) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])


def _body_scale(points: Mapping[str, tuple[float, float]]) -> float:
    candidates: list[float] = []
    for left, right in (
        ("left_shoulder", "right_shoulder"),
        ("left_hip", "right_hip"),
    ):
        if left in points and right in points:
            candidates.append(_distance(points[left], points[right]))
    if all(name in points for name in (
        "left_shoulder",
        "right_shoulder",
        "left_hip",
        "right_hip",
    )):
        shoulder_center = (
            (points["left_shoulder"][0] + points["right_shoulder"][0]) / 2,
            (points["left_shoulder"][1] + points["right_shoulder"][1]) / 2,
        )
        hip_center = (
            (points["left_hip"][0] + points["right_hip"][0]) / 2,
            (points["left_hip"][1] + points["right_hip"][1]) / 2,
        )
        candidates.append(_distance(shoulder_center, hip_center))
    return max([value for value in candidates if value > 0] or [1e-6])


def _top_quartile_mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values, reverse=True)
    count = max(1, ceil(len(ordered) * 0.25))
    return fmean(ordered[:count])


@dataclass(frozen=True)
class _PoseSample:
    frame_index: int
    points: dict[str, tuple[float, float]]
    body_scale: float


class MotionInputValidationRejected(RuntimeError):
    """A retryable presentation-safe rejection before formal scoring."""

    code = "INPUT_VALIDATION_FAILED"
    retryable = True

    def __init__(self, result: Mapping[str, Any]) -> None:
        self.result = dict(result)
        super().__init__(str(result.get("message") or USER_MESSAGES["INVALID"]))


class MotionInputValidator:
    """Collect explainable input-quality metrics from an existing Pose pass."""

    def __init__(
        self,
        assessment_type: str,
        *,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        self.config = dict(config or load_motion_input_validation_config())
        self.assessment_type = assessment_type.strip().lower()
        profiles = self.config.get("profiles") or {}
        if self.assessment_type not in profiles:
            raise ValueError(
                f"Unsupported motion input validation profile: {assessment_type}"
            )
        self.profile = dict(profiles[self.assessment_type])
        self.total_frames = 0
        self.detected_frames = 0
        self._body_completeness: list[float] = []
        self._upper_completeness: list[float] = []
        self._lower_completeness: list[float] = []
        self._motion_energy: list[float] = []
        self._previous: _PoseSample | None = None

    def _visible(self, landmark: Any) -> bool:
        point = _point(landmark)
        if point is None:
            return False
        margin = float(self.config["coordinate_margin"])
        return (
            _confidence(landmark) >= float(self.config["landmark_confidence"])
            and -margin <= point[0] <= 1.0 + margin
            and -margin <= point[1] <= 1.0 + margin
        )

    @staticmethod
    def _ratio(names: Sequence[str], visible: set[str]) -> float:
        return sum(name in visible for name in names) / len(names)

    def observe(self, landmarks: Sequence[Any] | None) -> None:
        frame_index = self.total_frames
        self.total_frames += 1
        if landmarks is None or len(landmarks) < 29:
            self._previous = None
            return

        self.detected_frames += 1
        points: dict[str, tuple[float, float]] = {}
        visible: set[str] = set()
        for name, index in LANDMARK_INDEX.items():
            point = _point(landmarks[index])
            if point is not None:
                points[name] = point
            if self._visible(landmarks[index]):
                visible.add(name)

        self._body_completeness.append(self._ratio(BODY_ANCHORS, visible))
        self._upper_completeness.append(self._ratio(UPPER_BODY, visible))
        self._lower_completeness.append(self._ratio(LOWER_BODY, visible))

        motion_names = tuple(self.profile["motion_landmarks"])
        motion_points = {
            name: points[name]
            for name in motion_names
            if name in visible and name in points
        }
        sample = _PoseSample(
            frame_index=frame_index,
            points=motion_points,
            body_scale=_body_scale(points),
        )
        previous = self._previous
        if previous is not None and frame_index - previous.frame_index == 1:
            shared = set(previous.points) & set(sample.points)
            if len(shared) >= 2:
                scale = max(
                    (previous.body_scale + sample.body_scale) / 2,
                    1e-6,
                )
                self._motion_energy.append(
                    fmean(
                        _distance(previous.points[name], sample.points[name])
                        / scale
                        for name in shared
                    )
                )
        self._previous = sample

    def build(self) -> dict[str, Any]:
        detection_ratio = (
            self.detected_frames / self.total_frames
            if self.total_frames
            else 0.0
        )
        body = fmean(self._body_completeness) if self._body_completeness else 0.0
        upper = fmean(self._upper_completeness) if self._upper_completeness else 0.0
        lower = fmean(self._lower_completeness) if self._lower_completeness else 0.0
        activity = _top_quartile_mean(self._motion_energy)

        reasons: list[str] = []
        invalid = (
            self.detected_frames
            < int(self.config["minimum_reliable_pose_frames"])
            or detection_ratio
            < float(self.config["invalid_below_pose_detection_ratio"])
        )
        if invalid:
            status = "INVALID"
            reasons.append("NO_RELIABLE_POSE")
        else:
            if detection_ratio < float(
                self.profile["minimum_pose_detection_ratio"]
            ):
                reasons.append("LOW_POSE_DETECTION")
            if body < float(
                self.profile["minimum_body_completeness_ratio"]
            ):
                reasons.append("INSUFFICIENT_BODY_VISIBILITY")
            if upper < float(
                self.profile["minimum_upper_body_completeness_ratio"]
            ):
                reasons.append("INSUFFICIENT_UPPER_BODY_VISIBILITY")
            if lower < float(
                self.profile["minimum_lower_body_completeness_ratio"]
            ):
                reasons.append("INSUFFICIENT_LOWER_BODY_VISIBILITY")
            if activity < float(self.profile["minimum_motion_activity"]):
                reasons.append("LOW_MOTION_ACTIVITY")
            status = "NEEDS_REVIEW" if reasons else "READY"

        return {
            "status": status,
            "validation_version": self.config["validation_version"],
            "threshold_status": self.config["status"],
            "assessment_type": self.assessment_type,
            "metrics": {
                "total_processed_frames": self.total_frames,
                "pose_detected_frames": self.detected_frames,
                "pose_detection_ratio": round(detection_ratio, 4),
                "body_completeness_ratio": round(body, 4),
                "upper_body_completeness_ratio": round(upper, 4),
                "lower_body_completeness_ratio": round(lower, 4),
                "motion_activity": round(activity, 4),
            },
            "reasons": reasons,
            "message": USER_MESSAGES[status],
            "retryable": status != "READY",
        }


def save_motion_input_validation(
    result: Mapping[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dict(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def require_motion_input_ready(result: Mapping[str, Any]) -> None:
    if result.get("status") != "READY":
        raise MotionInputValidationRejected(result)
