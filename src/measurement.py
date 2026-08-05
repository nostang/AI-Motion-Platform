"""
AI Motion Measurement

功能：
計算人體三個 Landmark 形成的關節角度。
"""

import math


def calculate_angle(point_a, point_b, point_c) -> float:

    """
    計算三個點形成的夾角。

    point_b 是角度的中心點。

    例如膝蓋角度：
        A = 髖部
        B = 膝蓋
        C = 腳踝

    回傳：
        0～180 度的角度
    """

    vector_ba = (
        point_a.x - point_b.x,
        point_a.y - point_b.y,
    )

    vector_bc = (
        point_c.x - point_b.x,
        point_c.y - point_b.y,
    )

    dot_product = (
        vector_ba[0] * vector_bc[0]
        + vector_ba[1] * vector_bc[1]
    )

    length_ba = math.sqrt(
        vector_ba[0] ** 2
        + vector_ba[1] ** 2
    )

    length_bc = math.sqrt(
        vector_bc[0] ** 2
        + vector_bc[1] ** 2
    )

    # 避免兩個點重疊時除以 0
    if length_ba == 0 or length_bc == 0:
        return 0.0

    cosine_angle = dot_product / (
        length_ba * length_bc
    )

    # 避免浮點誤差造成 acos 超出範圍
    cosine_angle = max(
        -1.0,
        min(1.0, cosine_angle),
    )

    angle_radians = math.acos(cosine_angle)

    return math.degrees(angle_radians)

def calculate_hip_center(left_hip, right_hip):

    """
    計算人體 Hip 中心點
    """

    center_x = (left_hip.x + right_hip.x) / 2
    center_y = (left_hip.y + right_hip.y) / 2

    return center_x, center_y

#把左右腳踝、腳跟、腳尖位置整理成固定格式
def get_foot_positions(landmarks) -> dict:
    """
    M003：取得左右腳位置。

    MediaPipe Landmark：
        27 = Left Ankle
        28 = Right Ankle
        29 = Left Heel
        30 = Right Heel
        31 = Left Foot Index
        32 = Right Foot Index
    """

    return {
        "left_ankle": {
            "x": landmarks[27].x,
            "y": landmarks[27].y,
            "visibility": landmarks[27].visibility,
        },
        "right_ankle": {
            "x": landmarks[28].x,
            "y": landmarks[28].y,
            "visibility": landmarks[28].visibility,
        },
        "left_heel": {
            "x": landmarks[29].x,
            "y": landmarks[29].y,
            "visibility": landmarks[29].visibility,
        },
        "right_heel": {
            "x": landmarks[30].x,
            "y": landmarks[30].y,
            "visibility": landmarks[30].visibility,
        },
        "left_foot_index": {
            "x": landmarks[31].x,
            "y": landmarks[31].y,
            "visibility": landmarks[31].visibility,
        },
        "right_foot_index": {
            "x": landmarks[32].x,
            "y": landmarks[32].y,
            "visibility": landmarks[32].visibility,
        },
    }

#算左右腳踝目前距離
def calculate_foot_distance(foot_positions: dict) -> float:
    """
    M004：計算左右腳踝之間的正規化距離。

    回傳值不是公尺或公分，而是影像正規化座標距離。
    """

    left_ankle = foot_positions["left_ankle"]
    right_ankle = foot_positions["right_ankle"]

    delta_x = right_ankle["x"] - left_ankle["x"]
    delta_y = right_ankle["y"] - left_ankle["y"]

    return math.sqrt(
        delta_x**2
        + delta_y**2
    )

def calculate_displacement(
    previous_point: tuple[float, float] | None,
    current_point: tuple[float, float],
) -> dict:
    """
    M005：計算骨盆中心位移。

    previous_point：
        前一幀骨盆中心的正規化座標 (x, y)

    current_point：
        目前幀骨盆中心的正規化座標 (x, y)

    第一幀沒有 previous_point，因此回傳 valid=False。
    """

    if previous_point is None:
        return {
            "delta_x": 0.0,
            "delta_y": 0.0,
            "distance": 0.0,
            "valid": False,
        }

    delta_x = current_point[0] - previous_point[0]
    delta_y = current_point[1] - previous_point[1]

    distance = math.sqrt(
        delta_x**2
        + delta_y**2
    )

    return {
        "delta_x": delta_x,
        "delta_y": delta_y,
        "distance": distance,
        "valid": True,
    }


def calculate_velocity(
    displacement: dict,
    delta_time_seconds: float,
) -> dict:
    """
    M006：計算骨盆中心移動速度。

    注意：
    回傳的是 normalized_per_second，
    不是公尺／秒。
    """

    if (
        not displacement["valid"]
        or delta_time_seconds <= 0
    ):
        return {
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "speed": 0.0,
            "unit": "normalized_per_second",
            "valid": False,
        }

    velocity_x = (
        displacement["delta_x"]
        / delta_time_seconds
    )

    velocity_y = (
        displacement["delta_y"]
        / delta_time_seconds
    )

    speed = (
        displacement["distance"]
        / delta_time_seconds
    )

    return {
        "velocity_x": velocity_x,
        "velocity_y": velocity_y,
        "speed": speed,
        "unit": "normalized_per_second",
        "valid": True,
    }

#用影片開始時的位置，建立中心基準
def calculate_center_reference(
    calibration_points: list[tuple[float, float]],
) -> tuple[float, float] | None:
    """
    根據校正期間收集的骨盆中心座標，
    計算中心基準位置。

    使用平均值建立：
        center_x
        center_y

    若沒有有效資料，回傳 None。
    """

    if not calibration_points:
        return None

    center_x = sum(
        point[0] for point in calibration_points
    ) / len(calibration_points)

    center_y = sum(
        point[1] for point in calibration_points
    ) / len(calibration_points)

    return center_x, center_y

#算目前位置距離中心多遠
def calculate_center_offset(
    current_point: tuple[float, float],
    center_reference: tuple[float, float],
) -> float:
    """
    計算目前骨盆中心與校正中心的距離。

    回傳值為正規化座標距離，
    不是公尺或公分。
    """

    delta_x = current_point[0] - center_reference[0]
    delta_y = current_point[1] - center_reference[1]

    return math.sqrt(
        delta_x**2
        + delta_y**2
    )

#判斷目前是否位於中心區域
def is_inside_center_region(
    center_offset: float,
    center_region_radius: float,
) -> bool:
    """
    判斷目前骨盆中心是否位於 Center Region。
    """

    return center_offset <= center_region_radius