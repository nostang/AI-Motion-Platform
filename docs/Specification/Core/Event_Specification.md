# Event Specification

Version: 1.0

Status: Stable

Platform:
AI Motion Platform

---

# Purpose

Event Layer 負責：

將一段完整人體動作

切分成

具有教學意義的 Teaching Phase。

Event Layer

不是：

人體辨識。

也不是：

評分。

而是：

描述目前人體動作進行到哪一個教學階段。

---

# Why

AI Coach

不應直接根據：

Pose

↓

Score

而是：

Pose

↓

Teaching Phase

↓

Feature

↓

Assessment

↓

Coach

Teaching Phase

是：

人體教學流程

與

AI Feature

之間的重要橋樑。

---

# Teaching Phase

所有 Motion

皆應拆分為：

Teaching Phase。

例如：

READY

↓

LOAD

↓

ROTATION

↓

EXECUTION

↓

FINISH

不同 Motion

可以：

新增

或

刪除

Phase。

但是：

Teaching Phase

的概念保持一致。

---

# Event Responsibility

Event Layer

負責：

✓ 偵測 Teaching Phase

✓ Phase Start

✓ Phase End

✓ Phase Duration

✓ Event 完整性

✓ Event 順序

---

Event Layer

不得：

✗ 評分

✗ 教學建議

✗ Report

✗ Coach

---

# Standard Event Output

所有 Motion

Event

統一：

{
    "phase": "...",
    "phase_id": "...",
    "start_frame": ...,
    "end_frame": ...,
    "duration": ...
}

---

# Event Order

Teaching Phase

必須：

保持合理順序。

例如：

READY

↓

LOAD

↓

ROTATION

↓

EXECUTION

↓

FINISH

不得：

READY

↓

FINISH

↓

LOAD

---

# Motion Example

Footwork

READY

↓

MOVE

↓

REACH

↓

RECOVERY

↓

READY

---

Forehand Serve

READY

↓

BACKSWING

↓

SWING

↓

FOLLOW_THROUGH

↓

FINISH

---

High Clear

READY

↓

LOAD

↓

ROTATION

↓

SWING

↓

FOLLOW_THROUGH

↓

FINISH

---

# Event Quality

Event Layer

只回答：

目前：

做到哪一步？

不回答：

做得好不好？

做得漂不漂亮？

是否得分？

---

# Assessment

Assessment

才回答：

每一個 Phase

是否完成品質要求。

---

# Future

L4

Teaching Phase

將支援：

Machine Learning

自動切分。

目前：

L3

Rule Based。