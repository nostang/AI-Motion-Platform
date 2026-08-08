"""Deterministic AI Summary Builder V1."""

from __future__ import annotations
from typing import Any, Mapping

MOTION_LABELS = {"footwork": "步法", "serve": "發球", "clear": "高遠球"}
DIRECTION_LABELS = {
    "IMPROVED": "進步",
    "DECLINED": "退步",
    "UNCHANGED": "持平",
    "NOT_INTERPRETED": "暫不解讀",
}

def build_ai_summary(summary: Mapping[str, Any], coach: Mapping[str, Any]) -> dict[str, Any]:
    motions = list(summary.get("motions") or [])
    strengths = list(coach.get("strengths") or [])
    priorities = list(coach.get("improvement_priorities") or [])
    training = list(coach.get("training_recommendations") or [])

    if not motions:
        return {"status": "NOT_READY", "reason": "NO_MOTION_RESULTS"}

    headline = _build_headline(strengths, motions)
    progress_summary = _build_progress_summary(motions)

    focus = [
        MOTION_LABELS.get(str(x.get("motion_type")), str(x.get("motion_type")))
        for x in priorities if x.get("motion_type")
    ]
    recommendations = [
        str(x["recommendation"]) for x in training if x.get("recommendation")
    ]

    return {
        "status": "READY",
        "headline": headline,
        "progress_summary": progress_summary,
        "focus": focus,
        "recommendations": recommendations,
        "evidence": {
            "strengths": strengths,
            "improvement_priorities": priorities,
        },
    }

def _build_headline(strengths, motions) -> str:
    if strengths:
        x = strengths[0]
        motion = str(x.get("motion_type") or "")
        label = MOTION_LABELS.get(motion, motion)
        score = x.get("score")
        return (
            f"{label}目前是相對優勢項目，分數為 {float(score):g} 分。"
            if score is not None else f"{label}目前是相對優勢項目。"
        )

    scored = [x for x in motions if x.get("score") is not None]
    if not scored:
        return "目前尚無足夠分數可建立能力摘要。"
    best = max(scored, key=lambda x: float(x["score"]))
    label = str(best.get("label") or best.get("motion_type") or "")
    return f"{label}目前在三項結果中分數較高。"

def _build_progress_summary(motions) -> str:
    ready = []
    first = []

    for x in motions:
        progress = x.get("progress")
        if not isinstance(progress, Mapping):
            continue
        label = str(x.get("label") or x.get("motion_type") or "")
        if progress.get("status") == "FIRST_RECORD":
            first.append(label)
        elif progress.get("status") == "READY":
            ready.append((label, str(progress.get("direction") or ""), progress.get("change")))

    if ready and len(ready) == len(motions) and all(d == "UNCHANGED" for _, d, _ in ready):
        return "三項目前皆與前一次持平。"

    parts = []
    for label, direction, change in ready:
        direction_label = DIRECTION_LABELS.get(direction, direction)
        if change is None:
            parts.append(f"{label}{direction_label}")
        else:
            delta = float(change)
            sign = "+" if delta > 0 else ""
            parts.append(f"{label}{direction_label}（{sign}{delta:g}）")

    if first:
        parts.append("、".join(first) + "為首次紀錄")

    return "；".join(parts) + "。" if parts else "目前沒有足夠的歷史資料可進行前次比較。"
