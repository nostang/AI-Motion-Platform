"""Video Input Normalization V1."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


class VideoNormalizationError(RuntimeError):
    pass


def build_ffmpeg_command(
    source_path: Path,
    output_path: Path,
) -> list[str]:
    source_path = Path(source_path)
    output_path = Path(output_path)

    return [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-vf",
        "scale=-2:'min(720,ih)'",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def normalize_for_analysis(
    source_path: Path,
    output_path: Path,
) -> Path:
    source_path = Path(source_path)
    output_path = Path(output_path)

    if not source_path.exists():
        raise VideoNormalizationError(
            f"找不到待正規化影片：{source_path}"
        )

    if shutil.which("ffmpeg") is None:
        raise VideoNormalizationError(
            "執行環境找不到 ffmpeg，無法執行 Video Input Normalization V1。"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    completed = subprocess.run(
        build_ffmpeg_command(source_path, output_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        output_path.unlink(missing_ok=True)
        stderr = (completed.stderr or "").strip()
        if len(stderr) > 1200:
            stderr = stderr[-1200:]
        raise VideoNormalizationError(
            "影片正規化失敗。"
            + (f" ffmpeg: {stderr}" if stderr else "")
        )

    if not output_path.exists() or output_path.stat().st_size <= 0:
        output_path.unlink(missing_ok=True)
        raise VideoNormalizationError(
            "影片正規化完成但輸出檔案無效。"
        )

    return output_path
