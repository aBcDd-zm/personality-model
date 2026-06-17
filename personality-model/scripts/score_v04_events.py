#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.v04_event_adapter import build_score_input_from_v04_event
from src.hybrid_scorer import score


SCORING_FIELDS = [
    "scored",
    "skip_reason",
    "rule_result",
    "llm_result",
    "hybrid_result",
    "final_result",
    "confidence",
    "evidence",
    "decision_style",
    "scoring_method",
    "scoring_trace",
]


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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if rows:
        event_fields = [field for field in rows[0] if field not in SCORING_FIELDS]
    else:
        event_fields = []
    fieldnames = event_fields + [field for field in SCORING_FIELDS if field not in event_fields]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _skip_reason(event: dict[str, Any]) -> list[str]:
    flags = event.get("quality_flags") or []
    if isinstance(flags, str):
        flags = [flag for flag in flags.split("|") if flag]
    if not flags:
        return ["invalid_event"]
    return list(flags)


def _blank_scoring_fields(
    event: dict[str, Any],
    *,
    scored: bool,
    skip_reason: list[str] | None,
) -> dict[str, Any]:
    row = dict(event)
    row.update(
        {
            "scored": scored,
            "skip_reason": skip_reason,
            "rule_result": None,
            "llm_result": None,
            "hybrid_result": None,
            "final_result": None,
            "confidence": None,
            "evidence": [],
            "decision_style": None,
            "scoring_method": None,
            "scoring_trace": None,
        }
    )
    return row


def score_event(event: dict[str, Any], *, method: str, use_llm: bool) -> dict[str, Any]:
    score_input = build_score_input_from_v04_event(event)
    result = score(score_input, method=method, use_llm=use_llm)
    result_payload = result.to_dict()
    row = dict(event)
    final_result = result_payload.get("final_result") or result_payload
    row.update(
        {
            "scored": True,
            "skip_reason": None,
            "rule_result": result_payload.get("rule_result"),
            "llm_result": result_payload.get("llm_result"),
            "hybrid_result": result_payload.get("hybrid_result"),
            "final_result": final_result,
            "confidence": result_payload.get("confidence"),
            "evidence": result_payload.get("evidence", []),
            "decision_style": result_payload.get("decision_style"),
            "scoring_method": result_payload.get("scoring_method"),
            "scoring_trace": result_payload.get("scoring_trace"),
        }
    )
    return row


def build_report(
    *,
    input_event_count: int,
    rows: list[dict[str, Any]],
    skipped_event_count: int,
    method: str,
    use_llm: bool,
) -> dict[str, Any]:
    scored_rows = [row for row in rows if row.get("scored")]
    confidences = [float(row["confidence"]) for row in scored_rows if row.get("confidence") is not None]
    fallback_counter = Counter(
        (row.get("scoring_trace") or {}).get("fallback_reason") or "NONE"
        for row in scored_rows
    )
    return {
        "input_event_count": input_event_count,
        "scored_event_count": len(scored_rows),
        "skipped_event_count": skipped_event_count,
        "method": method,
        "use_llm": use_llm,
        "llm_used_count": sum(
            1 for row in scored_rows if (row.get("scoring_trace") or {}).get("llm_used") is True
        ),
        "fallback_reason_distribution": dict(sorted(fallback_counter.items())),
        "average_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
    }


def score_v04_events(
    *,
    input_path: Path,
    output_path: Path,
    method: str = "hybrid",
    use_llm: bool = False,
    include_invalid: bool = True,
) -> dict[str, Any]:
    events = read_jsonl(input_path)
    rows: list[dict[str, Any]] = []
    skipped_event_count = 0

    for event in events:
        if event.get("is_valid_event") is True:
            rows.append(score_event(event, method=method, use_llm=use_llm))
            continue

        skipped_event_count += 1
        if include_invalid:
            rows.append(_blank_scoring_fields(event, scored=False, skip_reason=_skip_reason(event)))

    write_jsonl(output_path, rows)
    csv_path = output_path.with_suffix(".csv")
    report_path = output_path.with_name("v04_scoring_report.json")
    write_csv(csv_path, rows)
    report = build_report(
        input_event_count=len(events),
        rows=rows,
        skipped_event_count=skipped_event_count,
        method=method,
        use_llm=use_llm,
    )
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score v0.4 event JSONL with rule/llm/hybrid scorers.")
    parser.add_argument("--input", required=True, type=Path, help="Input v04_events.jsonl path")
    parser.add_argument("--output", required=True, type=Path, help="Output v04_scored_events.jsonl path")
    parser.add_argument("--method", choices=["rule", "llm", "hybrid"], default="hybrid")
    parser.add_argument("--use-llm", action="store_true", help="Allow real LLM scoring when env config is valid")
    parser.add_argument(
        "--include-invalid",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include invalid events as scored=false rows. Defaults to true.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = score_v04_events(
        input_path=args.input,
        output_path=args.output,
        method=args.method,
        use_llm=args.use_llm,
        include_invalid=args.include_invalid,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
