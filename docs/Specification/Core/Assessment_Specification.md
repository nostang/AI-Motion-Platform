# Assessment Specification

Version: 1.0

Status: Stable

Platform:
AI Motion Platform

---

# Purpose

Assessment Layer

負責：

根據 Teaching Specification

評估人體動作品質。

Assessment

不是：

姿勢辨識。

不是：

Feature Extraction。

而是：

將可量測的 Measurements

轉換成

具有教學意義的評估結果。

---

# Workflow

Teaching Specification

↓

Teaching Phase

↓

Observable Features

↓

Measurements

↓

Assessment Metrics

↓

Overall Score

---

# Assessment Responsibility

Assessment Layer

負責：

✓ Measurement Validation

✓ Metric Evaluation

✓ Metric Score

✓ Weight Calculation

✓ Overall Score

✓ Confidence

✓ Limitation

不得：

✗ 修改 Measurement

✗ 修改 Event

✗ Coach

✗ Report

---

# Assessment Unit

Platform

所有 Assessment

由：

Metric

組成。

例如：

Footwork

Recovery

Balance

Movement

Center Return

Serve

Preparation

Swing

Coordination

Follow-through

High Clear

Sideways Preparation

Weight Transfer

Non-racket Arm Balance

Swing Smoothness

---

# Metric

每個 Metric

包含：

Metric Name

Teaching Principle

Measurement

Weight

Score

Comment

例如：

Metric

↓

Weight Transfer

Teaching Principle

↓

重心轉移

Measurement

↓

hip_center_x_delta

Weight

↓

25

Score

↓

18

---

# Weight

Platform

所有 Motion

建議：

Total

100

例如：

25

25

25

25

未來：

可以：

20

20

20

20

20

依 Motion

調整。

---

# Overall Score

Overall Score

不是：

單一 Measurement。

而是：

Weighted Sum

↓

Normalization

↓

Overall

---

# Confidence

Confidence

代表：

AI

對此次評估的可信度。

影響因素：

Pose Detection Rate

Measurement Quality

Missing Landmark

Phase Completion

Confidence

不影響：

Score。

---

# Assessment Result

Assessment

至少輸出：

assessment_id

assessment_type

overall_score

metrics

confidence

limitations

---

# Assessment Rules

Assessment

必須：

Explainable

Repeatable

Deterministic

不得：

Random

Hidden Rule

Magic Number

---

# Calibration

Threshold

不得：

因：

單支影片

直接修改。

修改流程：

Problem

↓

Debug

↓

Root Cause

↓

Calibration

↓

Regression Test

---

# Future

L4

加入：

Adaptive Assessment

Coach Feedback Learning

Expert Calibration

Machine Learning Assisted Assessment

目前：

L3

Rule Based Assessment