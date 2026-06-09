import json
from pathlib import Path

from scripts.score_v04_events import score_v04_events


def make_event(event_id, *, is_valid_event=True, quality_flags=None, text=None):
    return {
        "event_id": event_id,
        "session_id": "S_P_001",
        "user_id": "P_001",
        "participant_id": "P_001",
        "scene_id": "SCENE_T1",
        "scene_name": "还好赶上晨会了",
        "task_id": "1",
        "task_name": "还好赶上晨会了",
        "target_traits": "外向性 E,开放性 O",
        "event_type": "main_answer",
        "prompt": "你会怎么回应？",
        "user_text": text if text is not None else "我会先确认风险，再推动团队合作完成交付。",
        "text_char_count": 20,
        "quality_flag_raw": "ok" if is_valid_event else "low_quality",
        "quality_flags": quality_flags or [],
        "is_low_quality": not is_valid_event,
        "is_valid_event": is_valid_event,
        "created_at": "2026-06-07T19:25:20+08:00",
    }


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_score_v04_events_scores_valid_and_skips_invalid(tmp_path, monkeypatch):
    def fail_if_called(score_input):
        raise AssertionError("LLM should not be called by default")

    monkeypatch.setattr("src.hybrid_scorer.score_with_llm", fail_if_called)
    input_path = tmp_path / "v04_events.jsonl"
    output_path = tmp_path / "v04_scored_events.jsonl"
    write_jsonl(
        input_path,
        [
            make_event("EV_P_001_T1_A1"),
            make_event("EV_P_001_T1_A2", is_valid_event=False, quality_flags=["too_short"], text="短"),
        ],
    )

    report = score_v04_events(input_path=input_path, output_path=output_path)
    rows = read_jsonl(output_path)

    assert len(rows) == 2
    assert rows[0]["scored"] is True
    assert rows[0]["final_result"] is not None
    assert rows[1]["scored"] is False
    assert rows[1]["skip_reason"] == ["too_short"]
    assert report["input_event_count"] == 2
    assert report["scored_event_count"] == 1
    assert report["skipped_event_count"] == 1
    assert report["use_llm"] is False
    assert report["llm_used_count"] == 0


def test_score_v04_events_writes_csv_and_report(tmp_path):
    input_path = tmp_path / "v04_events.jsonl"
    output_path = tmp_path / "v04_scored_events.jsonl"
    write_jsonl(input_path, [make_event("EV_P_001_T1_A1")])

    report = score_v04_events(input_path=input_path, output_path=output_path, method="hybrid")

    csv_path = tmp_path / "v04_scored_events.csv"
    report_path = tmp_path / "v04_scoring_report.json"
    assert csv_path.exists()
    assert report_path.exists()
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_report == report
    assert saved_report["method"] == "hybrid"
    assert saved_report["average_confidence"] is not None
