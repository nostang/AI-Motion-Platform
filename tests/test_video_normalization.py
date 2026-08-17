from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.api.video_normalization import (
    VideoNormalizationError,
    build_ffmpeg_command,
    normalize_for_analysis,
)


class VideoNormalizationV1Tests(unittest.TestCase):
    def test_command_uses_h264_720p_and_preserves_timing(self) -> None:
        command = build_ffmpeg_command(
            Path("/tmp/source.mov"),
            Path("/tmp/analysis_source.mp4"),
        )
        joined = " ".join(command)

        self.assertIn("libx264", command)
        self.assertIn("-crf", command)
        self.assertIn("-an", command)
        self.assertIn("+faststart", command)
        self.assertIn("min(720,ih)", joined)
        self.assertNotIn("-r", command)
        self.assertNotIn("fps=30", joined)
        self.assertNotIn("fps=", joined)

    @patch("src.api.video_normalization.shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("src.api.video_normalization.subprocess.run")
    def test_normalize_returns_output_path(
        self,
        run_mock,
        _which_mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mov"
            output = root / "analysis_source.mp4"
            source.write_bytes(b"source")

            def fake_run(*_args, **_kwargs):
                output.write_bytes(b"normalized")

                class Result:
                    returncode = 0
                    stderr = ""

                return Result()

            run_mock.side_effect = fake_run
            result = normalize_for_analysis(source, output)

            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            run_mock.assert_called_once()

    def test_missing_source_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(VideoNormalizationError):
                normalize_for_analysis(
                    root / "missing.mov",
                    root / "analysis_source.mp4",
                )


if __name__ == "__main__":
    unittest.main()
