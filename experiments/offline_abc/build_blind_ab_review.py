#!/usr/bin/env python3
"""Build a deterministic, provider-hidden A/B human review sheet."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_rows(a_run: dict, b_run: dict, seed: int = 20260927) -> tuple[list[dict], list[dict]]:
    combined = []
    for system, run in (("A", a_run), ("B", b_run)):
        for case in run["cases"]:
            combined.append({"system": system, "case": case})
    random.Random(seed).shuffle(combined)

    public_rows = []
    private_mapping = []
    for index, item in enumerate(combined, start=1):
        output_id = f"BLIND-{index:02d}"
        case = item["case"]
        response = case.get("response") or {}
        public_rows.append(
            {
                "blind_output_id": output_id,
                "case_id": case["case_id"],
                "evidence_kind": case.get("evidence_kind"),
                "motion": case.get("motion"),
                "scenario": case.get("scenario"),
                "input_score": case.get("input_overall_score"),
                "output_summary": _text(response.get("summary", "")),
                "output_strength": _text(response.get("strength", "")),
                "output_priority": _text(response.get("priority", "")),
                "output_drill": _text(response.get("drill", "")),
                "output_caution": _text(response.get("caution", "")),
                "human_grounding_1_to_5": "",
                "human_helpfulness_1_to_5": "",
                "human_clarity_1_to_5": "",
                "human_hallucination_yes_no": "",
                "reviewer_notes": "",
            }
        )
        private_mapping.append(
            {
                "blind_output_id": output_id,
                "system": item["system"],
                "case_id": case["case_id"],
            }
        )
    return public_rows, private_mapping


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a-run", type=Path, required=True)
    parser.add_argument("--b-run", type=Path, required=True)
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--mapping-json", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260927)
    args = parser.parse_args()

    public_rows, private_mapping = build_rows(
        json.loads(args.a_run.read_text(encoding="utf-8")),
        json.loads(args.b_run.read_text(encoding="utf-8")),
        args.seed,
    )
    args.review_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.review_csv.open("w", encoding="utf-8-sig", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(public_rows[0]))
        writer.writeheader()
        writer.writerows(public_rows)
    args.mapping_json.write_text(
        json.dumps(
            {
                "purpose": "private mapping; do not show reviewer before scoring",
                "seed": args.seed,
                "row_count": len(private_mapping),
                "mapping": private_mapping,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"review_rows": len(public_rows), "mapping_rows": len(private_mapping)}))


if __name__ == "__main__":
    main()
