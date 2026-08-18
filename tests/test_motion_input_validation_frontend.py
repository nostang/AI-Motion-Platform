from __future__ import annotations

from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_frontend_uses_friendly_input_validation_failure():
    result = subprocess.run(
        [
            "node",
            "--test",
            str(
                PROJECT_ROOT
                / "tests/js/test_motion_input_validation_api.js"
            ),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
