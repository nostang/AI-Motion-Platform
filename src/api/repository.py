"""Thread-safe, file-backed assessment task repository for API v1."""

from __future__ import annotations
import json
from pathlib import Path
from threading import RLock
from typing import Any

_REPORT_FILENAMES = {
    "footwork": "footwork_analysis_report.json",
    "serve": "serve_analysis_report.json",
    "clear": "clear_analysis_report.json",
}


class AssessmentRepository:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def task_dir(self, assessment_id: str) -> Path:
        return self.root / assessment_id

    def save(self, task: dict[str, Any]) -> None:
        with self._lock:
            directory = self.task_dir(task["assessment_id"])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "task.json").write_text(
                json.dumps(task, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def get(self, assessment_id: str) -> dict[str, Any] | None:
        path = self.task_dir(assessment_id) / "task.json"
        if not path.exists():
            return None
        with self._lock:
            return json.loads(path.read_text(encoding="utf-8"))

    def report(
        self,
        assessment_id: str,
        assessment_type: str | None = None,
    ) -> dict[str, Any] | None:
        resolved_type = assessment_type
        if resolved_type is None:
            task = self.get(assessment_id)
            if task is None:
                return None
            resolved_type = str(task.get("assessment_type", "")).strip().lower()

        filename = _REPORT_FILENAMES.get(resolved_type)
        if filename is None:
            return None

        path = self.task_dir(assessment_id) / "output" / filename
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
