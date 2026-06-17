#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.aggregation import CONFIDENCE_THRESHOLD, aggregate_scene_scores, aggregate_session_scores
from src.profile_updater import initial_profile, update_profile


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = _fieldnames(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def build_profile_updates(session_scores: list[dict[str, Any]], *, alpha: float = 0.2) -> list[dict[str, Any]]:
    profiles_by_user: dict[str, dict[str, float]] = {}
    rows: list[dict[str, Any]] = []
    sorted_sessions = sorted(
        session_scores,
        key=lambda row: ("" if row.get("user_id") is None else str(row.get("user_id")), "" if row.get("session_id") is None else str(row.get("session_id"))),
    )
    for session in sorted_sessions:
        user_id = str(session.get("user_id") or "")
        old_profile = profiles_by_user.get(user_id) or initial_profile()
        new_profile = update_profile(old_profile, session, alpha=alpha)
        profiles_by_user[user_id] = new_profile
        rows.append(
            {
                "session_id": session.get("session_id"),
                "user_id": session.get("user_id"),
                "session_score": session.get("session_score"),
                "session_confidence": session.get("session_confidence"),
                "old_profile": old_profile,
                "updated_profile": new_profile,
                "alpha": alpha,
                "aggregation_status": session.get("aggregation_status"),
            }
        )
    return rows


def build_report(
    *,
    input_scored_event_count: int,
    scene_scores: list[dict[str, Any]],
    session_scores: list[dict[str, Any]],
    profile_updates: list[dict[str, Any]],
    alpha: float,
) -> dict[str, Any]:
    session_confidences = [
        float(row["session_confidence"])
        for row in session_scores
        if row.get("session_confidence") is not None
    ]
    return {
        "input_scored_event_count": input_scored_event_count,
        "scene_score_count": len(scene_scores),
        "session_score_count": len(session_scores),
        "profile_update_count": len(profile_updates),
        "aggregated_event_count": sum(row.get("aggregated_event_count", 0) for row in session_scores),
        "skipped_event_count": sum(row.get("skipped_event_count", 0) for row in session_scores),
        "no_valid_scene_count": sum(1 for row in scene_scores if row.get("aggregation_status") == "no_valid_events"),
        "no_valid_session_count": sum(1 for row in session_scores if row.get("aggregation_status") == "no_valid_events"),
        "average_session_confidence": round(sum(session_confidences) / len(session_confidences), 4)
        if session_confidences
        else None,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "alpha": alpha,
    }


def aggregate_v04_scores(*, input_path: Path, output_dir: Path, alpha: float = 0.2) -> dict[str, Any]:
    events = read_jsonl(input_path)
    scene_scores = aggregate_scene_scores(events)
    session_scores = aggregate_session_scores(events)
    profile_updates = build_profile_updates(session_scores, alpha=alpha)
    report = build_report(
        input_scored_event_count=len(events),
        scene_scores=scene_scores,
        session_scores=session_scores,
        profile_updates=profile_updates,
        alpha=alpha,
    )

    outputs = {
        "v04_scene_scores": scene_scores,
        "v04_session_scores": session_scores,
        "v04_profile_updates": profile_updates,
    }
    for name, rows in outputs.items():
        write_jsonl(output_dir / f"{name}.jsonl", rows)
        write_csv(output_dir / f"{name}.csv", rows)

    report_path = output_dir / "v04_aggregation_report.json"
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate v0.4 scored events into scene, session, and profile rows.")
    parser.add_argument("--input", required=True, type=Path, help="Input v04_scored_events.jsonl path")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for aggregation outputs")
    parser.add_argument("--alpha", default=0.2, type=float, help="Profile smoothing alpha. Defaults to 0.2.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = aggregate_v04_scores(input_path=args.input, output_dir=args.output_dir, alpha=args.alpha)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
