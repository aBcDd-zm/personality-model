#!/usr/bin/env python3
"""Convert exported raw personality CSV data into v0.4 standard datasets."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "personality_dataset_20260609_143645.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

TRAITS = ("O", "C", "E", "A", "N")
RAW_TRAIT_FIELDS = {
    "O": "bfi_O",
    "C": "bfi_C",
    "E": "bfi_E",
    "A": "bfi_A",
    "N": "bfi_N",
}
BFI_QUESTION_FIELDS = [f"bfi_q{i}" for i in range(1, 31)]
FACET_FIELDS = [
    "facet_E_sociability",
    "facet_E_assertiveness",
    "facet_E_energy",
    "facet_A_compassion",
    "facet_A_respectfulness",
    "facet_A_trust",
    "facet_C_organization",
    "facet_C_productiveness",
    "facet_C_responsibility",
    "facet_N_anxiety",
    "facet_N_depression",
    "facet_N_emotional_volatility",
    "facet_O_aesthetic_sensitivity",
    "facet_O_intellectual_curiosity",
    "facet_O_creative_imagination",
]

LABEL_FIELDS = (
    [
        "user_id",
        "session_id",
        "participant_id",
        "age_group",
        "gender",
        "education",
        "bfi_version",
    ]
    + BFI_QUESTION_FIELDS
    + [f"bfi_{trait}_raw" for trait in TRAITS]
    + [f"bfi_{trait}_100" for trait in TRAITS]
    + [f"{field}_raw" for field in FACET_FIELDS]
    + [f"{field}_100" for field in FACET_FIELDS]
)

EVENT_FIELDS = [
    "event_id",
    "session_id",
    "user_id",
    "participant_id",
    "scene_id",
    "scene_name",
    "task_id",
    "task_name",
    "target_traits",
    "event_type",
    "prompt",
    "user_text",
    "text_char_count",
    "quality_flag_raw",
    "quality_flags",
    "is_low_quality",
    "is_valid_event",
    "created_at",
]

SESSION_FIELDS = [
    "session_id",
    "user_id",
    "participant_id",
    "bfi_version",
    "scene_count",
    "completed_scene_count",
    "event_count",
    "valid_event_count",
    "low_quality_event_count",
    "main_answer_count",
    "followup_answer_count",
    "created_at_min",
    "created_at_max",
    "is_effective_session",
    "is_complete_session",
    "quality_summary",
]


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def nullable(value: Any) -> str | None:
    text = clean(value)
    return text if text else None


def parse_float(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def score_to_100(value: Any) -> float | None:
    raw = parse_float(value)
    if raw is None:
        return None
    return round((raw - 1.0) / 4.0 * 100.0, 2)


def json_default(value: Any) -> Any:
    return value


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=json_default) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            csv_row = {}
            for field in fieldnames:
                value = row.get(field)
                if isinstance(value, list):
                    csv_row[field] = "|".join(value)
                elif isinstance(value, dict):
                    csv_row[field] = json.dumps(value, ensure_ascii=False, sort_keys=True)
                else:
                    csv_row[field] = value
            writer.writerow(csv_row)


def repeated_chars(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 10:
        return False
    if re.search(r"(.)\1{7,}", compact):
        return True
    counts = Counter(compact)
    most_common_count = counts.most_common(1)[0][1]
    return most_common_count / len(compact) >= 0.7


def possible_prompt_copy(user_text: str, prompt: str) -> bool:
    if len(user_text) < 30 or not prompt:
        return False
    if user_text in prompt:
        return True
    return SequenceMatcher(None, user_text, prompt).ratio() >= 0.85


PROMPT_COPY_FRAGMENTS = (
    "【场景背景】",
    "【心理小剧场】",
    "你会怎么回应",
    "请写出你",
    "请说明你为什么",
    "用户回答1",
    "用户回答2",
    "追问：",
    "此时负责人看向你说",
    "你会选择主动表达",
)

OFF_TASK_FRAGMENTS = (
    "题目设置",
    "这题目",
    "这个题目",
    "问卷",
    "40字",
    "字数",
    "好长好累",
    "又臭又长",
    "无语了",
    "懒死",
    "不好玩",
    "能不能不要这样",
    "不能自己搞几个能选",
    "电话手表",
    "睡觉睡觉",
    "大宝贝",
    "社保",
)


def off_task_or_complaint(user_text: str) -> bool:
    compact = re.sub(r"\s+", "", user_text or "")
    if len(compact) < 8:
        return False
    return any(fragment in compact for fragment in OFF_TASK_FRAGMENTS)


def prompt_fragment_copy(user_text: str) -> bool:
    compact = re.sub(r"\s+", "", user_text or "")
    if len(compact) < 20:
        return False
    return any(fragment in compact for fragment in PROMPT_COPY_FRAGMENTS)


def repeated_non_answer(user_text: str) -> bool:
    compact = re.sub(r"\s+", "", user_text or "")
    if not compact:
        return False
    if compact.count("我不知道") >= 2:
        return True
    if compact in {"不知道", "不清楚", "随便", "没有想法"}:
        return True
    return False


def quality_for_event(raw_quality: str, user_text: str, prompt: str) -> tuple[list[str], bool, bool]:
    flags: list[str] = []
    compact_len = len(re.sub(r"\s+", "", user_text))

    if raw_quality == "low_quality":
        flags.append("raw_low_quality")
    if not user_text:
        flags.append("empty_text")
    if user_text and compact_len < 10:
        flags.append("too_short")
    if repeated_chars(user_text):
        flags.append("repeated_chars")
    if possible_prompt_copy(user_text, prompt):
        flags.append("possible_prompt_copy")
    if prompt_fragment_copy(user_text):
        flags.append("prompt_fragment_copy")
    if repeated_non_answer(user_text):
        flags.append("repeated_non_answer")
    if off_task_or_complaint(user_text):
        flags.append("off_task_or_complaint")

    invalid_flags = {
        "raw_low_quality",
        "empty_text",
        "too_short",
        "repeated_chars",
        "possible_prompt_copy",
        "prompt_fragment_copy",
        "repeated_non_answer",
        "off_task_or_complaint",
    }

    is_low_quality = any(flag in invalid_flags for flag in flags)

    is_valid_event = (
        raw_quality == "ok"
        and bool(user_text)
        and compact_len >= 10
        and not any(flag in invalid_flags for flag in flags)
    )

    return flags, is_low_quality, is_valid_event


def make_label(row: dict[str, str]) -> dict[str, Any]:
    participant_id = clean(row.get("participant_id"))
    label: dict[str, Any] = {
        "user_id": participant_id,
        "session_id": f"S_{participant_id}",
        "participant_id": participant_id,
        "age_group": nullable(row.get("age_group")),
        "gender": nullable(row.get("gender")),
        "education": nullable(row.get("education")),
        "bfi_version": nullable(row.get("bfi_version")),
    }
    for field in BFI_QUESTION_FIELDS:
        label[field] = parse_float(row.get(field))
    for trait in TRAITS:
        source_field = RAW_TRAIT_FIELDS[trait]
        label[f"bfi_{trait}_raw"] = parse_float(row.get(source_field))
    for trait in TRAITS:
        source_field = RAW_TRAIT_FIELDS[trait]
        label[f"bfi_{trait}_100"] = score_to_100(row.get(source_field))
    for field in FACET_FIELDS:
        label[f"{field}_raw"] = parse_float(row.get(field))
    for field in FACET_FIELDS:
        label[f"{field}_100"] = score_to_100(row.get(field))
    return label


def make_event(row: dict[str, str], answer_index: int) -> dict[str, Any]:
    participant_id = clean(row.get("participant_id"))
    task_id = clean(row.get("task_id"))
    event_type = "main_answer" if answer_index == 1 else "followup_answer"
    prompt = clean(row.get("main_prompt" if answer_index == 1 else "followup_prompt"))
    user_text = clean(row.get("user_answer_1" if answer_index == 1 else "user_answer_2"))
    raw_quality = clean(row.get("quality_flag"))
    flags, is_low_quality, is_valid_event = quality_for_event(raw_quality, user_text, prompt)

    return {
        "event_id": f"EV_{participant_id}_T{task_id}_A{answer_index}",
        "session_id": f"S_{participant_id}",
        "user_id": participant_id,
        "participant_id": participant_id,
        "scene_id": f"SCENE_T{task_id}",
        "scene_name": nullable(row.get("task_name")),
        "task_id": task_id,
        "task_name": nullable(row.get("task_name")),
        "target_traits": nullable(row.get("target_traits")),
        "event_type": event_type,
        "prompt": prompt or None,
        "user_text": user_text or None,
        "text_char_count": len(user_text),
        "quality_flag_raw": raw_quality or None,
        "quality_flags": flags,
        "is_low_quality": is_low_quality,
        "is_valid_event": is_valid_event,
        "created_at": nullable(row.get("created_at")),
    }


def has_complete_bfi(label: dict[str, Any]) -> bool:
    if label.get("bfi_version") != "BFI-2-S":
        return False
    return all(label.get(field) is not None for field in BFI_QUESTION_FIELDS)


def make_sessions(
    rows_by_participant: dict[str, list[dict[str, str]]],
    events_by_participant: dict[str, list[dict[str, Any]]],
    labels_by_participant: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for participant_id in sorted(labels_by_participant):
        rows = rows_by_participant[participant_id]
        events = events_by_participant[participant_id]
        label = labels_by_participant[participant_id]
        scene_ids = {clean(row.get("task_id")) for row in rows if clean(row.get("task_id"))}
        completed_scene_ids = {
            clean(row.get("task_id"))
            for row in rows
            if clean(row.get("task_id"))
            and (clean(row.get("user_answer_1")) or clean(row.get("user_answer_2")))
        }
        created_values = sorted(
            clean(row.get("created_at")) for row in rows if clean(row.get("created_at"))
        )
        valid_count = sum(1 for event in events if event["is_valid_event"])
        low_quality_count = sum(1 for event in events if event["is_low_quality"])
        complete_bfi = has_complete_bfi(label)
        invalid_reasons = Counter(
            flag for event in events for flag in event["quality_flags"]
        )
        scene_count = len(scene_ids)
        completed_scene_count = len(completed_scene_ids)

        sessions.append(
            {
                "session_id": f"S_{participant_id}",
                "user_id": participant_id,
                "participant_id": participant_id,
                "bfi_version": label.get("bfi_version"),
                "scene_count": scene_count,
                "completed_scene_count": completed_scene_count,
                "event_count": len(events),
                "valid_event_count": valid_count,
                "low_quality_event_count": low_quality_count,
                "main_answer_count": sum(1 for event in events if event["event_type"] == "main_answer"),
                "followup_answer_count": sum(
                    1 for event in events if event["event_type"] == "followup_answer"
                ),
                "created_at_min": created_values[0] if created_values else None,
                "created_at_max": created_values[-1] if created_values else None,
                "is_effective_session": complete_bfi and completed_scene_count >= 5 and valid_count >= 5,
                "is_complete_session": complete_bfi and completed_scene_count >= 6 and valid_count >= 10,
                "quality_summary": {
                    "complete_bfi": complete_bfi,
                    "invalid_reasons_count": dict(sorted(invalid_reasons.items())),
                },
            }
        )
    return sessions


def make_quality_report(
    raw_rows: list[dict[str, str]],
    events: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    labels: list[dict[str, Any]],
) -> dict[str, Any]:
    invalid_reasons = Counter(
        flag for event in events for flag in event["quality_flags"]
    )
    return {
        "raw_row_count": len(raw_rows),
        "event_count": len(events),
        "session_count": len(sessions),
        "label_count": len(labels),
        "valid_event_count": sum(1 for event in events if event["is_valid_event"]),
        "low_quality_event_count": sum(1 for event in events if event["is_low_quality"]),
        "effective_session_count": sum(1 for session in sessions if session["is_effective_session"]),
        "complete_session_count": sum(1 for session in sessions if session["is_complete_session"]),
        "scene_distribution": dict(
            sorted(Counter(clean(row.get("task_id")) for row in raw_rows).items())
        ),
        "quality_flag_distribution": dict(
            sorted(Counter(clean(row.get("quality_flag")) or "missing" for row in raw_rows).items())
        ),
        "invalid_reasons_count": dict(sorted(invalid_reasons.items())),
        "bfi_version_distribution": dict(
            sorted(Counter(clean(label.get("bfi_version")) or "missing" for label in labels).items())
        ),
    }


def convert(input_path: Path, output_dir: Path) -> dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    with input_path.open(newline="", encoding="utf-8-sig") as f:
        raw_rows = list(csv.DictReader(f))

    labels_by_participant: dict[str, dict[str, Any]] = {}
    rows_by_participant: dict[str, list[dict[str, str]]] = defaultdict(list)
    events_by_participant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    events: list[dict[str, Any]] = []

    for row in raw_rows:
        participant_id = clean(row.get("participant_id"))
        if not participant_id:
            continue
        rows_by_participant[participant_id].append(row)
        labels_by_participant.setdefault(participant_id, make_label(row))
        for answer_index in (1, 2):
            event = make_event(row, answer_index)
            events.append(event)
            events_by_participant[participant_id].append(event)

    labels = [labels_by_participant[key] for key in sorted(labels_by_participant)]
    sessions = make_sessions(rows_by_participant, events_by_participant, labels_by_participant)
    report = make_quality_report(raw_rows, events, sessions, labels)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "v04_events.jsonl", events)
    write_jsonl(output_dir / "v04_sessions.jsonl", sessions)
    write_jsonl(output_dir / "v04_labels.jsonl", labels)
    write_csv(output_dir / "v04_events.csv", events, EVENT_FIELDS)
    write_csv(output_dir / "v04_sessions.csv", sessions, SESSION_FIELDS)
    write_csv(output_dir / "v04_labels.csv", labels, LABEL_FIELDS)
    with (output_dir / "v04_quality_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert raw exported CSV into v0.4 event/session/label datasets."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Raw CSV path. Defaults to {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory. Defaults to {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = convert(args.input, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
