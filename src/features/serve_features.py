"""正手發球教學動作 MVP 的可解釋 2D Pose 特徵。"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, degrees, hypot
from statistics import mean, median, pstdev
from typing import Any, Sequence

from src.features.dominant_hand import DominantHandTracker


def _point(landmark: Any) -> tuple[float, float]:
    return float(landmark.x), float(landmark.y)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _midpoint(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


@dataclass
class ServeFeatureTracker:
    """逐幀收集發球 MVP 所需特徵。"""

    racket_side: str | None = None
    samples: list[dict[str, float]] = field(default_factory=list)
    dominant_hand_tracker: DominantHandTracker = field(
        default_factory=DominantHandTracker
    )

    def __post_init__(self) -> None:
        if self.racket_side is None:
            return

        normalized = self.racket_side.strip().lower()

        if normalized not in {"left", "right"}:
            raise ValueError(
                "racket_side 必須是 left 或 right。"
            )

        self.racket_side = normalized

    def observe(self, landmarks: Sequence[Any], timestamp_ms: int) -> None:
        self.dominant_hand_tracker.observe(landmarks, timestamp_ms)

        left_shoulder = _point(landmarks[11])
        right_shoulder = _point(landmarks[12])
        left_hip = _point(landmarks[23])
        right_hip = _point(landmarks[24])
        left_wrist = _point(landmarks[15])
        right_wrist = _point(landmarks[16])

        shoulder_center = _midpoint(left_shoulder, right_shoulder)
        hip_center = _midpoint(left_hip, right_hip)
        torso_dx = shoulder_center[0] - hip_center[0]
        torso_dy = hip_center[1] - shoulder_center[1]
        torso_lean = degrees(atan2(torso_dx, max(abs(torso_dy), 1e-6)))

        left_wrist_radius = _distance(left_wrist, left_shoulder)
        right_wrist_radius = _distance(right_wrist, right_shoulder)
        active_side = (
            self.racket_side
            or (
                "right"
                if right_wrist_radius
                >= left_wrist_radius
                else "left"
            )
        )
        active_wrist = right_wrist if active_side == "right" else left_wrist
        active_shoulder = right_shoulder if active_side == "right" else left_shoulder

        self.samples.append(
            {
                "timestamp_ms": float(timestamp_ms),
                "shoulder_center_x": shoulder_center[0],
                "shoulder_center_y": shoulder_center[1],
                "hip_center_x": hip_center[0],
                "hip_center_y": hip_center[1],
                "torso_lean_degrees": torso_lean,
                "left_wrist_x": left_wrist[0],
                "left_wrist_y": left_wrist[1],
                "right_wrist_x": right_wrist[0],
                "right_wrist_y": right_wrist[1],
                "left_wrist_shoulder_distance": _distance(
                    left_wrist,
                    left_shoulder,
                ),
                "right_wrist_shoulder_distance": _distance(
                    right_wrist,
                    right_shoulder,
                ),
                # 保留舊欄位，避免舊資料使用者立即中斷。
                "active_wrist_x": active_wrist[0],
                "active_wrist_y": active_wrist[1],
                "wrist_shoulder_distance": _distance(
                    active_wrist,
                    active_shoulder,
                ),
                "active_side_right": (
                    1.0 if active_side == "right" else 0.0
                ),
            }
        )

    def build(self) -> dict[str, Any]:
        automatic_hand = (
            self.dominant_hand_tracker.build()
        )

        dominant_hand = automatic_hand

        if self.racket_side is not None:
            dominant_hand = {
                "status": "HUMAN_CONFIRMED",
                "feature_version": (
                    "dominant-hand-v0.1"
                ),
                "sample_count": len(
                    self.dominant_hand_tracker.samples
                ),
                "estimated": self.racket_side,
                "confidence": 1.0,
                "source": "HUMAN_ANNOTATION",
                "automatic_estimate": automatic_hand,
            }

        if len(self.samples) < 3:
            return {
                "status": "NOT_EVALUATED",
                "feature_version": "serve-feature-v0.5",
                "sample_count": len(self.samples),
                "reason": "INSUFFICIENT_POSE_SAMPLES",
                "dominant_hand": dominant_hand,
                "analysis_window": {
                    "status": "NOT_DETECTED",
                    "reason": "INSUFFICIENT_POSE_SAMPLES",
                },
            }

        sample_count = len(self.samples)

        def wrist_positions(
            side: str,
        ) -> list[tuple[float, float]]:
            return [
                (
                    sample[f"{side}_wrist_x"],
                    sample[f"{side}_wrist_y"],
                )
                for sample in self.samples
            ]

        def path_steps(
            positions: list[tuple[float, float]],
        ) -> list[float]:
            return [
                _distance(first, second)
                for first, second in zip(
                    positions,
                    positions[1:],
                )
            ]

        left_positions = wrist_positions("left")
        right_positions = wrist_positions("right")
        left_steps = path_steps(left_positions)
        right_steps = path_steps(right_positions)

        # 單次分析固定使用同一側手腕，避免逐幀左右切換
        # 造成不連續的假速度。
        left_total = sum(left_steps)
        right_total = sum(right_steps)
        active_side = (
            self.racket_side
            or (
                "right"
                if right_total >= left_total
                else "left"
            )
        )

        positions = (
            right_positions
            if active_side == "right"
            else left_positions
        )
        steps = path_steps(positions)

        positive_steps = [
            value
            for value in steps
            if value > 1e-6
        ]

        typical_step = (
            median(positive_steps)
            if positive_steps
            else 0.0
        )

        # 大幅瞬間位移通常來自剪輯、鏡頭切換或重播跳接，
        # 不應被視為真實揮拍。
        cut_threshold = max(
            0.12,
            typical_step * 4.0,
        )
        cut_flags = [
            value > cut_threshold
            for value in steps
        ]

        usable_steps = [
            value
            for value, is_cut in zip(
                steps,
                cut_flags,
            )
            if not is_cut
        ]

        peak_step = (
            max(usable_steps)
            if usable_steps
            else 0.0
        )
        active_threshold = max(
            0.0015,
            peak_step * 0.12,
        )

        # 尋找連續活動區段；容許最多三個短暫低速 Step，
        # 但剪輯跳接會強制切斷區段。
        segments: list[tuple[int, int]] = []
        segment_start: int | None = None
        last_active: int | None = None
        gap_count = 0

        def close_segment() -> None:
            nonlocal segment_start
            nonlocal last_active
            nonlocal gap_count

            if (
                segment_start is not None
                and last_active is not None
            ):
                segments.append(
                    (segment_start, last_active)
                )

            segment_start = None
            last_active = None
            gap_count = 0

        for index, (step, is_cut) in enumerate(
            zip(steps, cut_flags)
        ):
            if is_cut:
                close_segment()
                continue

            if step >= active_threshold:
                if segment_start is None:
                    segment_start = index

                last_active = index
                gap_count = 0
                continue

            if segment_start is not None:
                gap_count += 1

                if gap_count > 3:
                    close_segment()

        close_segment()

        if segments:
            def segment_score(
                segment: tuple[int, int],
            ) -> float:
                start, end = segment
                return sum(
                    step
                    for step, is_cut in zip(
                        steps[start:end + 1],
                        cut_flags[start:end + 1],
                    )
                    if not is_cut
                )

            selected_start, selected_end = max(
                segments,
                key=segment_score,
            )

            # Step i 連接 Sample i 與 i+1；
            # 前後各保留兩個 Sample 作為動作邊界。
            window_start = max(
                0,
                selected_start - 2,
            )
            window_end = min(
                sample_count - 1,
                selected_end + 3,
            )
            window_status = "DETECTED"
        else:
            window_start = 0
            window_end = sample_count - 1
            window_status = "FALLBACK_FULL_VIDEO"

        # Serve Feature Window V0.4
        #
        # 原始活動區段通常只涵蓋手腕高速移動的核心，
        # 因此必須向前保留準備、向後保留收拍。
        # 遇到剪輯跳接時不可跨越 Scene 邊界。
        minimum_window_ms = 1500
        preparation_padding_ms = 750
        follow_through_padding_ms = 900

        scene_start = 0
        scene_end = sample_count - 1

        for index in range(
            max(0, window_start - 1),
            -1,
            -1,
        ):
            if cut_flags[index]:
                scene_start = index + 1
                break

        for index in range(
            window_end,
            len(cut_flags),
        ):
            if cut_flags[index]:
                scene_end = index
                break

        selected_start_ms = self.samples[
            window_start
        ]["timestamp_ms"]
        selected_end_ms = self.samples[
            window_end
        ]["timestamp_ms"]

        desired_start_ms = (
            selected_start_ms
            - preparation_padding_ms
        )
        desired_end_ms = (
            selected_end_ms
            + follow_through_padding_ms
        )

        while (
            window_start > scene_start
            and self.samples[window_start][
                "timestamp_ms"
            ] > desired_start_ms
        ):
            window_start -= 1

        while (
            window_end < scene_end
            and self.samples[window_end][
                "timestamp_ms"
            ] < desired_end_ms
        ):
            window_end += 1

        # 如果固定 Padding 後仍不足 1.5 秒，
        # 便在同一個 Scene 內繼續向兩側延伸。
        while (
            self.samples[window_end]["timestamp_ms"]
            - self.samples[window_start]["timestamp_ms"]
            < minimum_window_ms
            and (
                window_start > scene_start
                or window_end < scene_end
            )
        ):
            if window_start > scene_start:
                window_start -= 1

            if (
                self.samples[window_end]["timestamp_ms"]
                - self.samples[window_start]["timestamp_ms"]
                >= minimum_window_ms
            ):
                break

            if window_end < scene_end:
                window_end += 1

        window_duration_ms = int(
            self.samples[window_end]["timestamp_ms"]
            - self.samples[window_start]["timestamp_ms"]
        )

        window_completeness = (
            "COMPLETE"
            if window_duration_ms >= minimum_window_ms
            else "INCOMPLETE_WINDOW"
        )

        window_samples = self.samples[
            window_start:window_end + 1
        ]
        window_positions = positions[
            window_start:window_end + 1
        ]
        window_steps = path_steps(window_positions)

        # 對應至原始 Step Index，排除剪輯跳接。
        valid_window_steps: list[float] = []

        for local_index, value in enumerate(
            window_steps
        ):
            original_index = (
                window_start + local_index
            )

            if (
                original_index < len(cut_flags)
                and not cut_flags[original_index]
            ):
                valid_window_steps.append(value)

        swing_path_length = sum(valid_window_steps)

        # 準備穩定使用主要揮拍前的最近樣本。
        prep_available = self.samples[:window_start]

        if len(prep_available) >= 3:
            prep_count = min(
                max(3, int(sample_count * 0.2)),
                len(prep_available),
            )
            prep = prep_available[-prep_count:]
        else:
            prep = self.samples[
                :min(3, sample_count)
            ]

        hip_x = [
            sample["hip_center_x"]
            for sample in prep
        ]
        hip_y = [
            sample["hip_center_y"]
            for sample in prep
        ]
        prep_stability = (
            pstdev(hip_x)
            + pstdev(hip_y)
        )

        shoulder_distance_key = (
            f"{active_side}_wrist_shoulder_distance"
        )
        extension_values = [
            sample[shoulder_distance_key]
            for sample in window_samples
        ]
        extension_range = (
            max(extension_values)
            - min(extension_values)
        )

        torso_values = [
            sample["torso_lean_degrees"]
            for sample in window_samples
        ]
        torso_change = (
            max(torso_values)
            - min(torso_values)
        )

        speeds: list[float] = []

        for local_index, (
            first,
            second,
        ) in enumerate(zip(
            window_samples,
            window_samples[1:],
        )):
            original_index = (
                window_start + local_index
            )

            if (
                original_index < len(cut_flags)
                and cut_flags[original_index]
            ):
                continue

            dt = (
                second["timestamp_ms"]
                - first["timestamp_ms"]
            ) / 1000.0

            if dt <= 0:
                continue

            displacement = _distance(
                window_positions[local_index],
                window_positions[local_index + 1],
            )
            speeds.append(displacement / dt)

        # 只在主要動作中的有效移動速度計算變異，
        # 排除前後靜止幀。CV 對均勻時間縮放保持不變。
        peak_speed = max(speeds) if speeds else 0.0
        moving_threshold = peak_speed * 0.08
        moving_speeds = [
            speed
            for speed in speeds
            if speed >= moving_threshold
            and speed > 1e-9
        ]

        mean_speed = (
            mean(moving_speeds)
            if moving_speeds
            else 0.0
        )
        speed_variation = (
            pstdev(moving_speeds) / mean_speed
            if (
                moving_speeds
                and mean_speed > 1e-9
            )
            else None
        )

        return {
            "status": "EXTRACTED",
            "feature_version": "serve-feature-v0.5",
            "sample_count": sample_count,
            "active_side_estimate": active_side,
            "dominant_hand": dominant_hand,
            "analysis_window": {
                "status": window_status,
                "start_sample": window_start,
                "end_sample": window_end,
                "sample_count": len(window_samples),
                "duration_ms": window_duration_ms,
                "completeness_status": window_completeness,
                "minimum_required_ms": minimum_window_ms,
                "start_ms": int(
                    window_samples[0]["timestamp_ms"]
                ),
                "end_ms": int(
                    window_samples[-1]["timestamp_ms"]
                ),
                "candidate_count": len(segments),
                "cut_count": sum(cut_flags),
            },
            "preparation_stability_index": round(
                prep_stability,
                6,
            ),
            "swing_path_length": round(
                swing_path_length,
                6,
            ),
            "wrist_extension_range": round(
                extension_range,
                6,
            ),
            "torso_change_degrees": round(
                torso_change,
                4,
            ),
            "wrist_speed_variation": (
                None
                if speed_variation is None
                else round(
                    speed_variation,
                    6,
                )
            ),
            "limitations": [
                "Uses one-camera 2D MediaPipe landmarks.",
                "Selects one dominant continuous wrist-motion window.",
                "Uniform playback-speed changes do not alter the normalized speed-variation ratio.",
                "Edited cuts and replay boundaries are estimated heuristically.",
                "Active racket arm is estimated from total wrist motion and does not use racket detection.",
                "Does not yet verify forehand versus backhand serve type.",
                "Does not evaluate grip, finger action, racket face, shuttle trajectory, contact point, or service legality.",
            ],
        }
