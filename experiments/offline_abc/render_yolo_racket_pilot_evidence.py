#!/usr/bin/env python3
"""Render local annotation audits and a public aggregate pilot figure."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FONT = font_manager.FontProperties(fname="/System/Library/Fonts/STHeiti Medium.ttc")
NAVY = "#17324D"
BLUE = "#2878B5"
TEAL = "#2A9D8F"
ORANGE = "#F4A261"
RED = "#D95D39"


def render_annotation_audits(manifest_path: Path, output_dir: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    case_ids = sorted({record["case_id"] for record in manifest["records"]})
    for case_id in case_ids:
        records = [record for record in manifest["records"] if record["case_id"] == case_id]
        columns = 3
        rows = math.ceil(len(records) / columns)
        fig, axes = plt.subplots(rows, columns, figsize=(12, rows * 4.2), facecolor="white")
        axes = list(getattr(axes, "flat", [axes]))
        for axis, record in zip(axes, records):
            image = Image.open(PROJECT_ROOT / record["source_frame_path"]).convert("RGB")
            axis.imshow(image)
            x1, y1, x2, y2 = record["box_xyxy"]
            axis.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec=ORANGE, lw=3))
            axis.set_title(
                f"#{record['sample_index']} {record['quality_tier']}\nIoU {record['teacher_iou']:.2f} / conf {record['mean_teacher_confidence']:.2f}",
                fontsize=10,
            )
            axis.axis("off")
        for axis in axes[len(records):]:
            axis.axis("off")
        fig.suptitle(
            f"{case_id}｜AI-assisted racket prelabels（不是人工 ground truth）",
            fontproperties=FONT,
            fontsize=17,
            color=NAVY,
        )
        fig.tight_layout(rect=[0, 0, 1, 0.95])
        fig.savefig(output_dir / f"{case_id}_annotation_audit.jpg", dpi=120, bbox_inches="tight")
        plt.close(fig)


def render_public_summary(summary_path: Path, output_path: Path) -> None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    baseline = summary["evaluation"]["baseline_pretrained_yolo26n"]
    tuned = summary["evaluation"]["finetuned_yolo26n"]
    training = summary["training"]

    fig, axes = plt.subplots(1, 3, figsize=(17, 6.8), facecolor="white")
    fig.suptitle(
        "YOLO26n 小型羽球拍微調｜預訓練 vs AI 輔助標註微調",
        fontproperties=FONT,
        fontsize=22,
        color=NAVY,
    )

    metric_names = ["Precision", "Recall", "AP50", "AP50-95"]
    baseline_values = [baseline[key] * 100 for key in ("precision", "recall", "ap50", "ap50_95")]
    tuned_values = [tuned[key] * 100 for key in ("precision", "recall", "ap50", "ap50_95")]
    x = list(range(len(metric_names)))
    axes[0].bar([value - 0.18 for value in x], baseline_values, 0.36, color=BLUE, label="官方預訓練")
    axes[0].bar([value + 0.18 for value in x], tuned_values, 0.36, color=TEAL, label="小型微調")
    axes[0].set_xticks(x, metric_names)
    axes[0].set_ylim(0, 112)
    axes[0].set_ylabel("測試集指標（%）", fontproperties=FONT)
    axes[0].set_title(
        f"{baseline['test_frames']} 張 provisional test frame",
        fontproperties=FONT,
        fontsize=14,
    )
    axes[0].legend(prop=FONT, loc="upper left")
    axes[0].grid(axis="y", alpha=0.2)
    for positions, values in (([v - 0.18 for v in x], baseline_values), ([v + 0.18 for v in x], tuned_values)):
        for position, value in zip(positions, values):
            axes[0].text(position, value + 2, f"{value:.0f}%", ha="center", fontsize=9)

    latency_names = ["p50", "p95"]
    base_latency = [baseline["p50_wall_seconds_per_frame"] * 1000, baseline["p95_wall_seconds_per_frame"] * 1000]
    tuned_latency = [tuned["p50_wall_seconds_per_frame"] * 1000, tuned["p95_wall_seconds_per_frame"] * 1000]
    lx = [0, 1]
    axes[1].bar([value - 0.18 for value in lx], base_latency, 0.36, color=BLUE, label="官方預訓練")
    axes[1].bar([value + 0.18 for value in lx], tuned_latency, 0.36, color=TEAL, label="小型微調")
    axes[1].set_xticks(lx, latency_names)
    axes[1].set_ylabel("ms / frame", fontproperties=FONT)
    axes[1].set_title("M5 Pro / MPS 推論時間", fontproperties=FONT, fontsize=14)
    axes[1].legend(prop=FONT, loc="upper left")
    axes[1].grid(axis="y", alpha=0.2)
    for positions, values in (([v - 0.18 for v in lx], base_latency), ([v + 0.18 for v in lx], tuned_latency)):
        for position, value in zip(positions, values):
            axes[1].text(position, value + max(base_latency + tuned_latency) * 0.025, f"{value:.1f}", ha="center", fontsize=9)

    axes[2].axis("off")
    axes[2].set_title("怎麼讀這次訓練", fontproperties=FONT, fontsize=14, color=NAVY)
    messages = [
        ("資料", f"72 張來源；嚴格共識標註 {summary['dataset']['included_consensus_frames']} 張\ntrain/val/test = {summary['dataset']['split_frames']['train']}/{summary['dataset']['split_frames']['val']}/{summary['dataset']['split_frames']['test']}"),
        ("訓練", f"YOLO26n transfer learning\n{training['epochs_completed']} epochs；{training['wall_seconds']:.1f} 秒"),
        ("限制", "標籤來自 26s＋26m 共識\n不是人工 ground truth，也沒有左手案例"),
        ("用途", "證明資料→訓練→測試流程\n不宣稱 production accuracy"),
    ]
    for index, (title, body) in enumerate(messages):
        y = 0.88 - index * 0.22
        axes[2].text(0.05, y, title, fontproperties=FONT, fontsize=13, color=NAVY)
        axes[2].text(0.05, y - 0.09, body, fontproperties=FONT, fontsize=10.5, color="#52606D")
        if index < len(messages) - 1:
            axes[2].plot([0.05, 0.95], [y - 0.15, y - 0.15], color="#CBD5E1", lw=1)

    fig.text(
        0.5,
        0.025,
        "這是 AI 輔助預標註的小樣本學習實驗；指標只能描述本資料集，不能當成人工驗證的正式準確率。",
        ha="center",
        fontproperties=FONT,
        fontsize=11.5,
        color=RED,
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.92])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--audit-dir", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    if args.manifest and args.audit_dir:
        render_annotation_audits(args.manifest, args.audit_dir)
    if args.summary and args.summary_output:
        render_public_summary(args.summary, args.summary_output)


if __name__ == "__main__":
    main()
