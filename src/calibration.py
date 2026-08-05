"""
Center Calibration

功能：
1. 收集影片開始時的骨盆中心位置
2. 建立 Center Reference
3. 判斷目前是否位於 Center Region
"""

from dataclasses import dataclass, field

from src.measurement import (
    calculate_center_offset,
    calculate_center_reference,
    is_inside_center_region,
)


@dataclass
class CenterCalibrationResult:
    """單一影格的中心校正結果。"""

    calibrated: bool
    calibrated_this_frame: bool
    center_reference: tuple[float, float] | None
    center_offset: float | None
    inside_center_region: bool | None
    progress: float


@dataclass
class CenterCalibrator:
    """管理影片開始階段的中心位置校正。"""

    calibration_frame_count: int
    center_region_radius: float
    calibration_points: list[tuple[float, float]] = field(
        default_factory=list
    )
    center_reference: tuple[float, float] | None = None
    calibrated: bool = False

    def update(
        self,
        hip_center: tuple[float, float],
    ) -> CenterCalibrationResult:
        """
        接收目前骨盆中心，更新校正狀態並回傳結果。
        """

        calibrated_this_frame = False

        if not self.calibrated:
            self.calibration_points.append(hip_center)

            if (
                len(self.calibration_points)
                >= self.calibration_frame_count
            ):
                self.center_reference = calculate_center_reference(
                    self.calibration_points
                )

                self.calibrated = self.center_reference is not None
                calibrated_this_frame = self.calibrated

        progress = min(
            1.0,
            len(self.calibration_points)
            / self.calibration_frame_count,
        )

        center_offset = None
        inside_center_region = None

        if self.calibrated and self.center_reference is not None:
            center_offset = calculate_center_offset(
                hip_center,
                self.center_reference,
            )

            inside_center_region = is_inside_center_region(
                center_offset,
                self.center_region_radius,
            )

        return CenterCalibrationResult(
            calibrated=self.calibrated,
            calibrated_this_frame=calibrated_this_frame,
            center_reference=self.center_reference,
            center_offset=center_offset,
            inside_center_region=inside_center_region,
            progress=progress,
        )
