"""End-to-end regression test for AI Motion Platform backend.

Requires:
- FastAPI server running locally
- DATABASE_URL configured in .env
- user_id=1 exists in PostgreSQL
- dataset videos:
  - dataset/footwork/videos/FW_001.mov
  - dataset/serve/videos/SV_002.mov
  - dataset/clear/videos/CL_003.mov

This script:
1. uploads Footwork / Serve / Clear
2. polls each assessment until completion
3. validates Competency
4. validates AI Coach
5. prints a compact PASS / FAIL summary
"""

from __future__ import annotations

import json
import mimetypes
import time
from pathlib import Path
from urllib import error, request


BASE_URL = "http://127.0.0.1:8000/api/v1"
USER_ID = 1
POLL_INTERVAL_SECONDS = 1.0
POLL_TIMEOUT_SECONDS = 120.0

TEST_CASES = {
    "footwork": Path("dataset/footwork/videos/FW_001.mov"),
    "serve": Path("dataset/serve/videos/SV_002.mov"),
    "clear": Path("dataset/clear/videos/CL_003.mov"),
}


def _http_json(
    method: str,
    url: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    req = request.Request(
        url,
        data=body,
        headers=headers or {},
        method=method,
    )

    try:
        with request.urlopen(req) as resp:
            payload = json.loads(
                resp.read().decode("utf-8")
            )
            return resp.status, payload
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def _multipart_body(
    fields: dict[str, str],
    file_field: str,
    file_path: Path,
) -> tuple[bytes, str]:
    boundary = "----AIMotionE2EBoundary"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; '
                    f'name="{name}"\r\n\r\n'
                ).encode(),
                str(value).encode(),
                b"\r\n",
            ]
        )

    content_type = (
        mimetypes.guess_type(file_path.name)[0]
        or "application/octet-stream"
    )

    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; '
                f'name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )

    return b"".join(chunks), boundary


def upload_assessment(
    motion_type: str,
    video_path: Path,
) -> str:
    if not video_path.exists():
        raise FileNotFoundError(
            f"Test video not found: {video_path}"
        )

    body, boundary = _multipart_body(
        {
            "assessment_type": motion_type,
            "user_id": str(USER_ID),
        },
        "video",
        video_path,
    )

    status, payload = _http_json(
        "POST",
        f"{BASE_URL}/motion-assessments",
        body=body,
        headers={
            "Content-Type": (
                f"multipart/form-data; boundary={boundary}"
            )
        },
    )

    if status != 202 or not payload.get("success"):
        raise RuntimeError(
            f"{motion_type} upload failed: "
            f"HTTP {status} {payload}"
        )

    return payload["data"]["assessment_id"]


def wait_for_completion(
    assessment_id: str,
) -> dict:
    deadline = time.time() + POLL_TIMEOUT_SECONDS

    while time.time() < deadline:
        status, payload = _http_json(
            "GET",
            (
                f"{BASE_URL}/motion-assessments/"
                f"{assessment_id}"
            ),
        )

        if status != 200 or not payload.get("success"):
            raise RuntimeError(
                f"status query failed: "
                f"HTTP {status} {payload}"
            )

        data = payload["data"]
        state = data.get("status")

        if state == "completed":
            return data

        if state == "failed":
            raise RuntimeError(
                f"assessment failed: {data}"
            )

        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"assessment timeout: {assessment_id}"
    )


def validate_competency() -> dict:
    status, payload = _http_json(
        "POST",
        f"{BASE_URL}/users/{USER_ID}/competency",
    )

    if status != 200 or not payload.get("success"):
        raise RuntimeError(
            f"competency failed: "
            f"HTTP {status} {payload}"
        )

    data = payload["data"]
    profile = data["profile"]
    interpretation = data["interpretation"]

    if profile.get("profile_status") != "COMPLETE":
        raise AssertionError(
            "Competency profile is not COMPLETE."
        )

    if interpretation.get("status") != "READY":
        raise AssertionError(
            "Competency interpretation is not READY."
        )

    return data


def validate_coach() -> dict:
    status, payload = _http_json(
        "POST",
        f"{BASE_URL}/users/{USER_ID}/coach",
    )

    if status != 200 or not payload.get("success"):
        raise RuntimeError(
            f"AI Coach failed: "
            f"HTTP {status} {payload}"
        )

    data = payload["data"]

    if data.get("status") != "READY":
        raise AssertionError(
            "AI Coach status is not READY."
        )

    return data


def main() -> None:
    assessment_ids: dict[str, str] = {}
    results: dict[str, dict] = {}

    print("=== AI Motion E2E Test ===")

    for motion_type, video_path in TEST_CASES.items():
        print(f"[UPLOAD] {motion_type}: {video_path}")
        assessment_id = upload_assessment(
            motion_type,
            video_path,
        )
        assessment_ids[motion_type] = assessment_id

        print(
            f"[WAIT] {motion_type}: "
            f"{assessment_id}"
        )

        results[motion_type] = wait_for_completion(
            assessment_id
        )

        print(
            f"[PASS] {motion_type}: "
            f"{assessment_id}"
        )

    competency = validate_competency()
    coach = validate_coach()

    profile = competency["profile"]

    print()
    print("=== Summary ===")

    for motion_type in ("footwork", "serve", "clear"):
        item = profile["motions"][motion_type]
        print(
            f"{motion_type.title()}: PASS "
            f"(score={item.get('overall_score')})"
        )

    print(
        "Competency: "
        f"{profile.get('profile_status')}"
    )

    print(
        "AI Coach: "
        f"{coach.get('status')}"
    )

    print()
    print("E2E RESULT: PASS")


if __name__ == "__main__":
    main()
