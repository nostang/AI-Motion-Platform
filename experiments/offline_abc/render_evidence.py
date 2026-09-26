#!/usr/bin/env python3
"""Render versioned evidence figures from the experiment JSON summaries."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
ASSETS = HERE / "assets"
FONT = font_manager.FontProperties(fname="/System/Library/Fonts/STHeiti Medium.ttc")
MONO = font_manager.FontProperties(family="monospace")
NAVY = "#17324D"
BLUE = "#2878B5"
TEAL = "#2A9D8F"
ORANGE = "#F4A261"
RED = "#D95D39"
PALE = "#F4F7FA"


def _json(name: str) -> dict:
    return json.loads((RESULTS / name).read_text())


def _box(ax, x, y, w, h, text, color=BLUE, size=13):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", fc=color, ec="none"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color="white", fontproperties=FONT, fontsize=size)


def _arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=18, lw=2, color=NAVY))


def option_a() -> None:
    media = _json("mediapipe_serve_baseline.json")
    cost = _json("option_a_cost_estimate.json")
    fig = plt.figure(figsize=(15, 8), facecolor="white")
    ax = fig.add_axes([0.04, 0.12, 0.92, 0.78])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.suptitle("方案 A｜雲端 MediaPipe + 雲端 LLM：證據與尚未測項", fontproperties=FONT, fontsize=22, color=NAVY)
    labels = ["1. 上傳影片", "2. MediaPipe\n擷取人體骨架", "3. 規則引擎\n固定分數", "4. 雲端 LLM\n只負責解說", "5. 報告畫面"]
    colors = [NAVY, BLUE, TEAL, ORANGE, NAVY]
    xs = [0.02, 0.215, 0.41, 0.605, 0.8]
    for x, label, color in zip(xs, labels, colors):
        _box(ax, x, 0.65, 0.16, 0.16, label, color)
    for x in (0.18, 0.375, 0.57, 0.765):
        _arrow(ax, x, 0.73, x + 0.035, 0.73)

    ax.text(0.03, 0.5, "已實測：共用 MediaPipe 核心", fontproperties=FONT, fontsize=16, color=NAVY)
    cards = [
        ("影片長度", f'{media["video"]["duration_seconds"]:.3f} 秒'),
        ("三次平均處理", f'{media["aggregate"]["mean_wall_seconds"]:.3f} 秒'),
        ("平均速度", f'{media["aggregate"]["mean_processed_fps"]:.1f} FPS'),
        ("峰值記憶體", f'{media["runs"][0]["peak_rss_mb"]:.1f} MB'),
    ]
    for index, (label, value) in enumerate(cards):
        x = 0.03 + index * 0.235
        ax.add_patch(FancyBboxPatch((x, 0.27), 0.2, 0.16, boxstyle="round,pad=0.02", fc=PALE, ec="#D9E2EC"))
        ax.text(x + 0.1, 0.37, label, ha="center", fontproperties=FONT, fontsize=11, color="#52606D")
        ax.text(x + 0.1, 0.31, value, ha="center", fontproperties=FONT, fontsize=18, color=NAVY)
    scenario = cost["scenario"]
    ax.text(0.03, 0.17, f'估算情境：10,000 次/月約 US${scenario["combined_usd_per_month"]:.3f}（不含儲存、網路、DB、重試）', fontproperties=FONT, fontsize=14, color=ORANGE)
    ax.text(0.03, 0.09, "尚未實測：雲端冷啟動、網路延遲、雲端 LLM 品質與實際帳單；需隔離測試專案補驗。", fontproperties=FONT, fontsize=13, color=RED)
    fig.savefig(ASSETS / "a_pipeline_evidence.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def option_b() -> None:
    gpu = _json("gemma4_three_cases.json")
    cpu = _json("gemma4_cpu_only.json")
    gpu_warm = [c["client_wall_seconds"] for c in gpu["cases"] if c["load_seconds"] < 0.1]
    cpu_warm = [c["client_wall_seconds"] for c in cpu["cases"] if c["load_seconds"] < 0.1]
    values = {
        "GPU warm latency": sum(gpu_warm) / len(gpu_warm),
        "CPU warm latency": sum(cpu_warm) / len(cpu_warm),
        "GPU tokens/s": gpu["aggregate"]["mean_tokens_per_second"],
        "CPU tokens/s": cpu["aggregate"]["mean_tokens_per_second"],
        "GPU resident GB": gpu["resource"]["resident_size_bytes"] / 1e9,
        "CPU resident GB": cpu["resource"]["resident_size_bytes"] / 1e9,
    }
    fig, axes = plt.subplots(1, 3, figsize=(15, 6), facecolor="white")
    fig.suptitle("方案 B｜地端 MediaPipe + 地端 Gemma 4：設備實測", fontproperties=FONT, fontsize=22, color=NAVY)
    panels = [
        ([values["GPU warm latency"], values["CPU warm latency"]], "暖機後每筆解說（秒）", [BLUE, ORANGE]),
        ([values["GPU tokens/s"], values["CPU tokens/s"]], "文字生成速度（tokens/s）", [BLUE, ORANGE]),
        ([values["GPU resident GB"], values["CPU resident GB"]], "模型常駐大小（GB）", [BLUE, ORANGE]),
    ]
    for ax, (vals, title, colors) in zip(axes, panels):
        bars = ax.bar(["Apple GPU", "CPU only"], vals, color=colors, width=0.62)
        ax.set_title(title, fontproperties=FONT, fontsize=14, color=NAVY)
        ax.grid(axis="y", alpha=0.2)
        for bar, value in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:.2f}", ha="center", va="bottom", fontsize=12)
    fig.text(0.5, 0.025, "同一台 Apple M5 Pro / 24 GB；三種報告皆成功輸出可解析 JSON。16 GB 是最低建議，24 GB 較適合實驗。", ha="center", fontproperties=FONT, fontsize=13, color=NAVY)
    fig.tight_layout(rect=[0, 0.07, 1, 0.9])
    fig.savefig(ASSETS / "b_equipment_benchmark.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    example = gpu["cases"][0]
    fig = plt.figure(figsize=(13, 7), facecolor="#111827")
    fig.text(0.04, 0.93, "Gemma 4 本機輸出畫面（SV_001）", fontproperties=FONT, fontsize=20, color="white")
    displayed = json.dumps({"case_id": example["case_id"], "checks": example["checks"], "response": example["response"]}, ensure_ascii=False, indent=2)
    fig.text(0.04, 0.87, displayed, fontproperties=FONT, fontsize=10.5, color="#D1FAE5", va="top")
    fig.text(0.04, 0.035, "原始證據：results/gemma4_three_cases.json", fontproperties=FONT, fontsize=11, color="#93C5FD")
    fig.savefig(ASSETS / "b_output_screen.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    concurrency = _json("gemma4_concurrency.json")
    one, two = concurrency["levels"]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor="white")
    fig.suptitle("方案 B｜多人使用與租用 VM 的依據", fontproperties=FONT, fontsize=22, color=NAVY)
    labels = ["1 個同時請求", "2 個同時請求"]
    latency = [one["aggregate"]["mean_request_wall_seconds"], two["aggregate"]["mean_request_wall_seconds"]]
    throughput = [one["aggregate"]["mean_requests_per_second"], two["aggregate"]["mean_requests_per_second"]]
    x = [0, 1]
    axes[0].bar([i - 0.18 for i in x], latency, width=0.36, color=BLUE, label="平均延遲（秒）")
    axes[0].bar([i + 0.18 for i in x], throughput, width=0.36, color=ORANGE, label="吞吐（requests/s）")
    axes[0].set_xticks(x, labels, fontproperties=FONT)
    axes[0].set_title("兩筆一起來：等待變長，吞吐沒有增加", fontproperties=FONT, fontsize=14)
    axes[0].legend(prop=FONT)
    axes[0].grid(axis="y", alpha=0.2)
    for i, value in enumerate(latency):
        axes[0].text(i - 0.18, value, f"{value:.2f}", ha="center", va="bottom")
    for i, value in enumerate(throughput):
        axes[0].text(i + 0.18, value, f"{value:.3f}", ha="center", va="bottom")

    vm_labels = ["CPU VM\n4 vCPU / 16 GiB", "L4 GPU VM\n4 vCPU / 16 GiB"]
    vm_monthly = [0.194236 * 730, 0.706832276 * 730]
    bars = axes[1].bar(vm_labels, vm_monthly, color=[ORANGE, RED], width=0.58)
    axes[1].set_title("若 24/7 租用：官方標價情境（US$/月）", fontproperties=FONT, fontsize=14)
    axes[1].set_xticks(range(2), vm_labels, fontproperties=FONT)
    axes[1].grid(axis="y", alpha=0.2)
    for bar, value in zip(bars, vm_monthly):
        axes[1].text(bar.get_x() + bar.get_width() / 2, value, f"${value:.2f}", ha="center", va="bottom", fontsize=12)
    fig.text(0.5, 0.025, "VM 未建立、速度未實測；金額是 2026-09-26 公開隨用隨付價格 × 730 小時，不含磁碟、網路與維運。", ha="center", fontproperties=FONT, fontsize=12, color=RED)
    fig.tight_layout(rect=[0, 0.07, 1, 0.9])
    fig.savefig(ASSETS / "b_concurrency_vm.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def option_c() -> None:
    yolo = _json("yolov12_tiny_feasibility.json")
    sample_path = RESULTS / "yolo_workspace" / "dataset" / "images" / "val" / yolo["inference"]["sample"]
    label_path = RESULTS / "yolo_workspace" / "dataset" / "labels" / "val" / f"{sample_path.stem}.txt"
    image = Image.open(sample_path).convert("RGB")
    cls, cx, cy, width, height = map(float, label_path.read_text().split())
    iw, ih = image.size
    left = (cx - width / 2) * iw
    top = (cy - height / 2) * ih
    box_width, box_height = width * iw, height * ih

    fig, axes = plt.subplots(1, 3, figsize=(16, 6), facecolor="white")
    fig.suptitle("方案 C｜官方 YOLOv12：已跑通流程，但尚未得到可用羽球模型", fontproperties=FONT, fontsize=21, color=NAVY)
    axes[0].imshow(image)
    axes[0].add_patch(Rectangle((left, top), box_width, box_height, fill=False, ec=RED, lw=3))
    axes[0].text(left, max(2, top - 4), "synthetic_target", color="white", backgroundcolor=RED, fontsize=10)
    axes[0].set_title("實際訓練資料畫面（合成）", fontproperties=FONT, fontsize=14)
    axes[0].axis("off")

    labels = ["訓練秒數", "模型 MB", "峰值 RSS/10"]
    vals = [yolo["training"]["wall_seconds"], yolo["training"]["model_size_bytes"] / 1e6, yolo["training"]["peak_process_rss_mb"] / 10]
    bars = axes[1].bar(labels, vals, color=[BLUE, TEAL, ORANGE])
    axes[1].set_xticks(range(len(labels)), labels, fontproperties=FONT)
    axes[1].set_title("流程數字（12 train + 4 val, 1 epoch）", fontproperties=FONT, fontsize=13)
    for bar, value in zip(bars, vals):
        axes[1].text(bar.get_x() + bar.get_width() / 2, value, f"{value:.1f}", ha="center", va="bottom")
    axes[1].text(0.5, 0.87, "mAP50 = 0\nPrecision = 0\nRecall = 0", transform=axes[1].transAxes, ha="center", va="top", fontproperties=FONT, fontsize=15, color=RED)
    axes[1].grid(axis="y", alpha=0.2)

    axes[2].axis("off")
    axes[2].set_title("下一階段的三條羽球研究路線", fontproperties=FONT, fontsize=14, color=NAVY)
    routes = [
        (0.75, "持拍手判定", "球拍框 + MediaPipe 手腕\n評估：左右手正確率"),
        (0.48, "球路徑", "逐幀羽球小物件框/點\n評估：偵測率、軌跡中斷率"),
        (0.21, "落點分析", "場地校正 + 落地幀/點\n評估：落點誤差、公分/區域"),
    ]
    for y, title, body in routes:
        axes[2].add_patch(FancyBboxPatch((0.08, y - 0.08), 0.84, 0.18, boxstyle="round,pad=0.02", fc=PALE, ec="#BCCCDC"))
        axes[2].text(0.13, y + 0.035, title, fontproperties=FONT, fontsize=14, color=NAVY)
        axes[2].text(0.13, y - 0.035, body, fontproperties=FONT, fontsize=11, color="#52606D")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    fig.savefig(ASSETS / "c_feasibility_research.png", dpi=170, bbox_inches="tight")
    plt.close(fig)

    training_text = """$ python benchmark_yolov12.py --epochs 1 --device mps
source commit: 2abab7153a065fb2925e8088e9ca2b19016ab7d6
dataset: 12 train / 4 validation / 1 class / 160 px

Epoch 1/1
train/box_loss: 6.62131
train/cls_loss: 4.57899
train/dfl_loss: 4.51259

validation images: 4
precision: 0
recall: 0
mAP50: 0
mAP50-95: 0

training wall time: 26.9749 s
best.pt: 5,381,802 bytes
result: pipeline completed; model accuracy NOT established"""
    fig = plt.figure(figsize=(13, 7), facecolor="#111827")
    fig.text(0.04, 0.93, "YOLOv12 訓練結果畫面（由原始 log / CSV / JSON 重建）", fontproperties=FONT, fontsize=19, color="white")
    fig.text(0.04, 0.86, training_text, fontproperties=MONO, fontsize=13, color="#D1FAE5", va="top", linespacing=1.35)
    fig.text(0.04, 0.035, "原始證據：results/yolo_workspace/.../results.csv + results/yolov12_tiny_feasibility.json", fontproperties=FONT, fontsize=11, color="#93C5FD")
    fig.savefig(ASSETS / "c_training_result_screen.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def decision() -> None:
    rows = ["沿用既有固定評分", "低規格終端可使用", "集中更新/回滾", "目前已有品質證據", "需要自行標註訓練"]
    cols = ["A 雲端 MP+LLM", "B 地端 MP+Gemma", "C 自訓 YOLOv12"]
    matrix = [
        ["通過", "通過", "未通過"],
        ["通過", "未通過", "尚未證明"],
        ["通過", "較困難", "可行但未建立"],
        ["核心通過；雲端待測", "通過", "僅流程；mAP=0"],
        ["不需要", "不需要", "需要"],
    ]
    colors = {"通過": "#D1FAE5", "不需要": "#D1FAE5", "未通過": "#FEE2E2", "較困難": "#FEF3C7", "尚未證明": "#FEF3C7", "核心通過；雲端待測": "#FEF3C7", "僅流程；mAP=0": "#FEE2E2", "可行但未建立": "#FEF3C7", "需要": "#FEE2E2"}
    fig, ax = plt.subplots(figsize=(15, 7), facecolor="white")
    ax.axis("off")
    table = ax.table(cellText=matrix, rowLabels=rows, colLabels=cols, cellLoc="center", loc="center", colWidths=[0.24, 0.24, 0.24])
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 2.2)
    for (row, col), cell in table.get_celld().items():
        cell.get_text().set_fontproperties(FONT)
        if row == 0:
            cell.set_facecolor(NAVY)
            cell.get_text().set_color("white")
        elif col >= 0:
            cell.set_facecolor(colors.get(cell.get_text().get_text(), "white"))
    fig.suptitle("選擇 A 的證據閘門（不是把估算偽裝成實測）", fontproperties=FONT, fontsize=22, color=NAVY)
    fig.text(0.5, 0.06, "結論：A 最符合現階段產品條件；但雲端 LLM 與端到端延遲仍必須在隔離環境補驗。", ha="center", fontproperties=FONT, fontsize=14, color=RED)
    fig.savefig(ASSETS / "abc_decision_evidence.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    option_a()
    option_b()
    option_c()
    decision()


if __name__ == "__main__":
    main()
