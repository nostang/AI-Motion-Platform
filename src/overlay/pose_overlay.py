"""共用 Pose 與狀態 Overlay。"""

from __future__ import annotations

from typing import Any, Sequence

import cv2

# MediaPipe Pose 33 點連線；避免依賴額外 drawing_utils 版本差異。
_POSE_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10), (11, 12),
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
)


def draw_pose_landmarks(
    frame: Any,
    landmarks: Sequence[Any],
    *,
    minimum_visibility: float = 0.35,
) -> None:
    """把正規化 Pose landmarks 畫到 BGR 影格。"""

    height, width = frame.shape[:2]
    points: list[tuple[int, int] | None] = []
    for landmark in landmarks:
        visibility = float(getattr(landmark, "visibility", 1.0))
        if visibility < minimum_visibility:
            points.append(None)
            continue
        x = int(float(landmark.x) * width)
        y = int(float(landmark.y) * height)
        points.append((x, y))

    for start, end in _POSE_CONNECTIONS:
        if start >= len(points) or end >= len(points):
            continue
        a, b = points[start], points[end]
        if a is not None and b is not None:
            cv2.line(frame, a, b, (70, 220, 120), 2, cv2.LINE_AA)

    for point in points:
        if point is not None:
            cv2.circle(frame, point, 3, (40, 180, 255), -1, cv2.LINE_AA)


def draw_status_panel(
    frame: Any,
    *,
    title: str,
    lines: Sequence[str],
    detected: bool,
) -> None:
    """顯示一致的動作名稱、Pose 狀態與即時資訊。"""

    panel_lines = [title, f"Pose: {'DETECTED' if detected else 'NOT DETECTED'}", *lines]
    width = min(frame.shape[1] - 20, 470)
    height = 18 + 29 * len(panel_lines)
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (10 + width, 10 + height), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.62, frame, 0.38, 0, frame)

    for index, text in enumerate(panel_lines):
        color = (80, 230, 120) if index == 1 and detected else (235, 235, 235)
        if index == 1 and not detected:
            color = (80, 80, 255)
        cv2.putText(
            frame,
            str(text),
            (22, 38 + index * 29),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.67,
            color,
            2,
            cv2.LINE_AA,
        )
