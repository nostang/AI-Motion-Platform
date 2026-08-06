# High Clear Teaching Specification

Version: 1.0

Status: Draft

Platform:
AI Motion Platform L3

Motion ID:
CL

---

# Purpose

本模組目的為：

評估高遠球教學動作是否符合基本教學原則。

本模組評估：

人體動作品質（Teaching Motion Quality）

而不是：

擊球結果（Shot Outcome）。

---

# Teaching Goal

建立初學者正確的高遠球動作鏈。

協助使用者：

- 建立正確揮拍動作
- 建立身體協調
- 建立重心轉移
- 建立完整揮拍

---

# Core Teaching Principles

## TP-01

Sideways Preparation

充分側身。

---

## TP-02

Weight Transfer

完成重心轉移。

---

## TP-03

Non-racket Arm Balance

非持拍手協助平衡與帶動。

---

## TP-04

Swing Smoothness

揮拍自然且舒展。

---

# Observable Features

## OF-01

Shoulder Rotation

對應：

TP-01

---

## OF-02

Hip Shift

對應：

TP-02

---

## OF-03

Non-racket Arm Motion

對應：

TP-03

---

## OF-04

Swing Path

對應：

TP-04

---

# Measurements

目前 MVP：

## shoulder_rotation_angle

肩膀旋轉角度。

---

## hip_center_x_delta

髖部中心位移。

---

## non_racket_arm_height

非持拍手高度。

---

## wrist_path_length

持拍手腕路徑。

---

# Assessment Metrics

| Metric | Weight |
|---------|-------:|
| Sideways Preparation | 25 |
| Weight Transfer | 25 |
| Non-racket Arm Balance | 25 |
| Swing Smoothness | 25 |

Overall：

100

---

# Coach Output

Coach 可以提供：

- 側身不足
- 重心轉移不足
- 左手未協助平衡
- 揮拍不夠舒展

不得：

重新計分。

---

# Not Evaluated

目前 MVP 不評估：

- 球拍
- 羽球
- 擊球點
- 落點
- 球速
- 擊球是否成功
- 手指發力
- 握拍方式

---

# Dataset

Dataset：

CL_001.mov

要求：

- Single Camera
- Full Body
- Stable Background
- Teaching Motion
- One Complete High Clear Swing

---

# Known Limitations

目前：

MediaPipe Pose

Single Camera

2D Landmark

不代表：

專業生物力學分析。

---

# Definition of Done

完成條件：

✓ Event

✓ Features

✓ Assessment

✓ Coach

✓ Report

✓ Validator

全部 PASS。
