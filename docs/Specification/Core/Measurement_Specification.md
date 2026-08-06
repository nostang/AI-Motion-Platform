# Measurement Specification

Version: 1.0

Status: Stable

Platform:
AI Motion Platform

---

# Purpose

Measurement Layer

負責：

將人體 Pose Landmark

轉換為

可量測的數值（Measurements）。

Measurement

是：

Observable Feature

與

Assessment

之間的橋樑。

---

# Workflow

Pose Landmark

↓

Measurement

↓

Observable Feature

↓

Assessment

---

# Measurement Responsibility

Measurement Layer

負責：

✓ Landmark

✓ Distance

✓ Angle

✓ Rotation

✓ Velocity

✓ Timing

✓ Path

✓ Stability

✓ Symmetry

---

不得：

✗ 評分

✗ Coach

✗ Report

✗ Event

---

# Measurement Types

## Position

例如：

Hip Center

Shoulder Center

Wrist

Ankle

---

## Distance

例如：

Foot Distance

Step Length

Arm Extension

---

## Angle

例如：

Shoulder Rotation

Torso Rotation

Hip Rotation

Elbow Angle

---

## Motion

例如：

Velocity

Acceleration

Movement Direction

---

## Path

例如：

Wrist Path

Foot Path

Hip Path

---

## Timing

例如：

Duration

Peak Velocity Time

Phase Duration

---

# Naming Convention

Measurement

全部使用：

snake_case

例如：

shoulder_rotation_angle

hip_center_x_delta

wrist_path_length

step_length

body_sway

---

# Measurement Rules

Measurement

永遠：

只描述

數值。

例如：

✓

shoulder_rotation_angle

= 42°

✓

step_length

= 0.85m

不得：

score

good

excellent

pass

---

# Measurement Quality

Measurement

必須：

Repeatable

Observable

Deterministic

Explainable

---

# Measurement Version

Measurement

應具有：

measurement_version

方便：

Calibration

Regression Test

---

# Future

L4

加入：

3D Measurement

Depth

Multi-camera

目前：

L3

Single Camera

MediaPipe Pose