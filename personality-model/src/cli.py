from __future__ import annotations

import argparse
import json
from pathlib import Path

from .hybrid_scorer import score
from .report_builder import build_session_report
from .schemas import ScoreInput


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Score workplace personality events from JSONL.")
    parser.add_argument("--input", required=True, help="Input sample_events.jsonl path")
    parser.add_argument("--output", required=True, help="Output scored_events.jsonl path")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    with output_path.open("w", encoding="utf-8") as handle:
        for payload in read_jsonl(input_path):
            score_input = ScoreInput.from_dict(payload)
            result = score(score_input)
            results.append(result)
            handle.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")

    report = build_session_report(results)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

