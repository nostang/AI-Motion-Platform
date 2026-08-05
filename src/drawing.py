"""
AI Motion Drawing Utilities

功能：
1. 繪製人體骨架與 Landmark
2. 顯示膝蓋角度、雙腳間距、骨盆位移與速度
3. 顯示 Center Region、校正狀態與骨盆中心軌跡
"""

from collections import deque

import cv2

from src.measurement import (
    calculate_angle,
    calculate_foot_distance,
    get_foot_positions,
)


# MediaPipe Pose 主要骨架連線
POSE_CONNECTIONS = [
    # 上半身
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),

    # 軀幹
    (11, 23),
    (12, 24),
    (23, 24),

    # 左腿
    (23, 25),
    (25, 27),
    (27, 29),
    (29, 31),
    (27, 31),

    # 右腿
    (24, 26),
    (26, 28),
    (28, 30),
    (30, 32),
    (28, 32),
]


def draw_pose_landmarks(frame, landmarks) -> None:
    """把 33 個 Landmark 與骨架畫到影片畫面。"""

    height, width = frame.shape[:2]
    pixel_points: list[tuple[int, int]] = []

    for landmark in landmarks:
        x = int(landmark.x * width)
        y = int(landmark.y * height)
        pixel_points.append((x, y))

    for start_index, end_index in POSE_CONNECTIONS:
        cv2.line(
            frame,
            pixel_points[start_index],
            pixel_points[end_index],
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

    for x, y in pixel_points:
        cv2.circle(
            frame,
            (x, y),
            4,
            (0, 0, 255),
            -1,
            cv2.LINE_AA,
        )


def draw_knee_angles(frame, landmarks) -> None:
    """計算並顯示左右膝關節角度。"""

    left_knee_angle = calculate_angle(
        landmarks[23],
        landmarks[25],
        landmarks[27],
    )

    right_knee_angle = calculate_angle(
        landmarks[24],
        landmarks[26],
        landmarks[28],
    )

    cv2.putText(
        frame,
        f"Left Knee: {left_knee_angle:.1f} deg",
        (20, 120),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        f"Right Knee: {right_knee_angle:.1f} deg",
        (20, 155),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def draw_foot_distance(frame, landmarks) -> None:
    """顯示左右腳踝的正規化距離。"""

    foot_positions = get_foot_positions(landmarks)
    foot_distance = calculate_foot_distance(foot_positions)

    cv2.putText(
        frame,
        f"Foot Distance: {foot_distance:.3f}",
        (20, 190),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def draw_pelvis_motion(
    frame,
    displacement: dict,
    velocity: dict,
) -> None:
    """顯示骨盆中心位移與速度。"""

    cv2.putText(
        frame,
        f"Pelvis Move: {displacement['distance']:.4f}",
        (20, 225),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        f"Pelvis Speed: {velocity['speed']:.4f} /s",
        (20, 260),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def draw_center_region(
    frame,
    center_reference: tuple[float, float],
    center_region_radius: float,
) -> None:
    """
    繪製正規化 Center Region。

    x、y 分別依照畫面寬高換算，因此以橢圓呈現。
    """

    height, width = frame.shape[:2]

    center_x = int(center_reference[0] * width)
    center_y = int(center_reference[1] * height)

    radius_x = max(1, int(center_region_radius * width))
    radius_y = max(1, int(center_region_radius * height))

    cv2.ellipse(
        frame,
        (center_x, center_y),
        (radius_x, radius_y),
        0,
        0,
        360,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        "Center Region",
        (center_x + 12, center_y - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )


def draw_center_status(
    frame,
    calibrated: bool,
    inside_center: bool | None,
    calibration_progress: float,
) -> None:
    """顯示中心校正進度與 INSIDE／OUTSIDE 狀態。"""

    if not calibrated:
        progress_percent = min(100, int(calibration_progress * 100))
        status_text = f"Center Calibrating: {progress_percent}%"
    elif inside_center:
        status_text = "Center Status: INSIDE"
    else:
        status_text = "Center Status: OUTSIDE"

    cv2.putText(
        frame,
        status_text,
        (20, 295),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def get_hip_center_pixel(
    frame,
    hip_center_normalized: tuple[float, float],
) -> tuple[int, int]:
    """把正規化骨盆中心轉成影片像素座標。"""

    height, width = frame.shape[:2]

    return (
        int(hip_center_normalized[0] * width),
        int(hip_center_normalized[1] * height),
    )


def draw_hip_center(
    frame,
    center_point: tuple[int, int],
) -> None:
    """在畫面上標示目前骨盆中心。"""

    pixel_x, pixel_y = center_point

    cv2.circle(
        frame,
        (pixel_x, pixel_y),
        9,
        (255, 0, 0),
        -1,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        "Pelvis Center",
        (pixel_x + 12, pixel_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 0, 0),
        2,
        cv2.LINE_AA,
    )


def draw_trajectory(
    frame,
    trajectory: deque,
) -> None:
    """把最近的骨盆中心位置連成移動軌跡。"""

    if len(trajectory) < 2:
        return

    points = list(trajectory)

    for index in range(1, len(points)):
        cv2.line(
            frame,
            points[index - 1],
            points[index],
            (255, 255, 0),
            3,
            cv2.LINE_AA,
        )


def draw_frame_info(
    frame,
    status_text: str,
    frame_index: int,
) -> None:
    """顯示 Pose 偵測狀態與 Frame Index。"""

    cv2.putText(
        frame,
        status_text,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        f"Frame: {frame_index}",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def draw_footwork_state(
    frame,
    state_text: str,
    event_id: int,
    move_time_seconds: float | None,
    recovery_time_seconds: float | None,
    total_time_seconds: float | None,
) -> None:
    """
    顯示 Footwork State 與 Event 時間。
    """

    cv2.putText(
        frame,
        f"Footwork State: {state_text}",
        (20, 330),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        f"Event ID: {event_id}",
        (20, 365),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    if move_time_seconds is None:
        move_text = "Move Time: --"
    else:
        move_text = (
            f"Move Time: "
            f"{move_time_seconds:.2f} sec"
        )

    if recovery_time_seconds is None:
        recovery_text = "Recovery Time: --"
    else:
        recovery_text = (
            f"Recovery Time: "
            f"{recovery_time_seconds:.2f} sec"
        )

    if total_time_seconds is None:
        total_text = "Total Time: --"
    else:
        total_text = (
            f"Total Time: "
            f"{total_time_seconds:.2f} sec"
        )

    cv2.putText(
        frame,
        move_text,
        (20, 400),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        recovery_text,
        (20, 435),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.putText(
        frame,
        total_text,
        (20, 470),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
