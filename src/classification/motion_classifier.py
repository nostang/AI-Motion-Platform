"""
Motion Classification V2

以 Center Reference 到 Reach Point 的位移向量進行八方向分類，
並輸出分類信心值。

注意：這仍是正面單鏡頭 2D 的 L3 簡化版。
信心值代表「系統對方向分類的確定程度」，不代表動作品質。
"""

from dataclasses import dataclass
from enum import Enum
from math import atan2, degrees, hypot


class MotionDirection(str, Enum):
    FRONT = "FRONT"
    RIGHT_FRONT = "RIGHT_FRONT"
    RIGHT = "RIGHT"
    RIGHT_BACK = "RIGHT_BACK"
    BACK = "BACK"
    LEFT_BACK = "LEFT_BACK"
    LEFT = "LEFT"
    LEFT_FRONT = "LEFT_FRONT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DirectionResult:
    direction: MotionDirection
    image_dx: float
    image_dy: float
    player_dx: float
    player_dy: float
    vector_length: float
    angle_degrees: float | None
    confidence: float
    valid: bool


class MotionClassifier:
    """以 Center → Reach 向量進行八方向分類。"""

    def __init__(
        self,
        *,
        mirror_x: bool,
        x_scale: float,
        y_scale: float,
        min_vector_length: float,
        min_confidence: float,
    ) -> None:
        if x_scale <= 0 or y_scale <= 0:
            raise ValueError("x_scale 與 y_scale 必須大於 0。")
        if min_vector_length < 0:
            raise ValueError("min_vector_length 不可小於 0。")
        if not 0 <= min_confidence <= 1:
            raise ValueError("min_confidence 必須介於 0 與 1。")

        self.mirror_x = mirror_x
        self.x_scale = x_scale
        self.y_scale = y_scale
        self.min_vector_length = min_vector_length
        self.min_confidence = min_confidence

    def classify(
        self,
        *,
        center_reference: tuple[float, float],
        reach_point: tuple[float, float],
    ) -> DirectionResult:
        image_dx = reach_point[0] - center_reference[0]
        image_dy = reach_point[1] - center_reference[1]

        player_dx = -image_dx if self.mirror_x else image_dx
        player_dy = image_dy

        scaled_dx = player_dx * self.x_scale
        scaled_dy = player_dy * self.y_scale
        vector_length = hypot(scaled_dx, scaled_dy)

        if vector_length < self.min_vector_length:
            return DirectionResult(
                direction=MotionDirection.UNKNOWN,
                image_dx=image_dx,
                image_dy=image_dy,
                player_dx=scaled_dx,
                player_dy=scaled_dy,
                vector_length=vector_length,
                angle_degrees=None,
                confidence=0.0,
                valid=False,
            )

        angle = degrees(atan2(scaled_dy, scaled_dx))
        raw_direction = self._direction_from_angle(angle)
        confidence = self._calculate_confidence(
            angle=angle,
            vector_length=vector_length,
        )

        direction = (
            raw_direction
            if confidence >= self.min_confidence
            else MotionDirection.UNKNOWN
        )

        return DirectionResult(
            direction=direction,
            image_dx=image_dx,
            image_dy=image_dy,
            player_dx=scaled_dx,
            player_dy=scaled_dy,
            vector_length=vector_length,
            angle_degrees=angle,
            confidence=confidence,
            valid=direction is not MotionDirection.UNKNOWN,
        )

    def _calculate_confidence(
        self,
        *,
        angle: float,
        vector_length: float,
    ) -> float:
        """
        以角度接近分類中心的程度與向量長度估算信心值。

        這是可解釋的工程信心值，不是模型機率。
        """

        sector_centers = (0, 45, 90, 135, 180, -135, -90, -45)
        angular_error = min(
            abs(((angle - center + 180) % 360) - 180)
            for center in sector_centers
        )
        angle_confidence = max(0.0, 1.0 - angular_error / 22.5)

        strong_vector_length = max(self.min_vector_length * 3.0, 0.12)
        vector_confidence = min(
            1.0,
            max(
                0.0,
                (vector_length - self.min_vector_length)
                / (strong_vector_length - self.min_vector_length),
            ),
        )

        return round(
            0.75 * angle_confidence + 0.25 * vector_confidence,
            4,
        )

    @staticmethod
    def _direction_from_angle(angle: float) -> MotionDirection:
        if -22.5 <= angle < 22.5:
            return MotionDirection.RIGHT
        if 22.5 <= angle < 67.5:
            return MotionDirection.RIGHT_FRONT
        if 67.5 <= angle < 112.5:
            return MotionDirection.FRONT
        if 112.5 <= angle < 157.5:
            return MotionDirection.LEFT_FRONT
        if angle >= 157.5 or angle < -157.5:
            return MotionDirection.LEFT
        if -157.5 <= angle < -112.5:
            return MotionDirection.LEFT_BACK
        if -112.5 <= angle < -67.5:
            return MotionDirection.BACK
        return MotionDirection.RIGHT_BACK
