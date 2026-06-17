import csv
import json
from pathlib import Path

from scripts.aggregate_v04_scores import aggregate_v04_scores
from src.aggregation import TRAIT_FIELDS


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def make_event(event_id, *, scene_id="SCENE_1", confidence=0.5, score=50, is_valid_event=True):
    return {
        "event_id": event_id,
        "session_id": "S_1",
        "user_id": "U_1",
        "scene_id": scene_id,
        "scene_name": "Scene",
        "task_id": scene_id[-1],
        "scored": is_valid_event,
        "is_valid_event": is_valid_event,
        "is_low_quality": not is_valid_event,
        "confidence": confidence if is_valid_event else None,
        "evidence": [{"quote": event_id}],
        "final_result": {"estimated_persona": {field: score for field in TRAIT_FIELDS}} if is_valid_event else None,
    }


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_aggregate_v04_scores_writes_outputs_and_report(tmp_path):
    input_path = tmp_path / "v04_scored_events.jsonl"
    write_jsonl(
        input_path,
        [
            make_event("E1", scene_id="SCENE_1", confidence=0.5, score=40),
            make_event("E2", scene_id="SCENE_2", confidence=0.5, score=60),
            make_event("E3", scene_id="SCENE_2", is_valid_event=False),
        ],
    )

    report = aggregate_v04_scores(input_path=input_path, output_dir=tmp_path)

    for filename in [
        "v04_scene_scores.jsonl",
        "v04_session_scores.jsonl",
        "v04_profile_updates.jsonl",
    ]:
        rows = read_jsonl(tmp_path / filename)
        assert rows

    for filename in [
        "v04_scene_scores.csv",
        "v04_session_scores.csv",
        "v04_profile_updates.csv",
    ]:
        with (tmp_path / filename).open("r", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle))
        assert "index" not in header
        assert "" not in header

    saved_report = json.loads((tmp_path / "v04_aggregation_report.json").read_text(encoding="utf-8"))
    assert saved_report == report
    assert report["input_scored_event_count"] == 3
    assert report["scene_score_count"] == 2
    assert report["session_score_count"] == 1
    assert report["profile_update_count"] == 1
    assert report["aggregated_event_count"] == 2
    assert report["skipped_event_count"] == 1
    assert report["no_valid_scene_count"] == 0
    assert report["no_valid_session_count"] == 0
    assert report["average_session_confidence"] == 0.5
    assert report["confidence_threshold"] == 0.2
    assert report["alpha"] == 0.2
