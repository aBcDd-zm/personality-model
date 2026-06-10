#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


TRAITS = {
    "O": ("personality_openness", "bfi_O_100"),
    "C": ("personality_conscientiousness", "bfi_C_100"),
    "E": ("personality_extraversion", "bfi_E_100"),
    "A": ("personality_agreeableness", "bfi_A_100"),
    "N": ("personality_neuroticism", "bfi_N_100"),
}


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_json_cell(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j + 2) / 2
        for k in range(i, j + 1):
            result[indexed[k][0]] = avg_rank
        i = j + 1
    return result


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    return pearson(ranks(xs), ranks(ys))


def round_or_blank(value: float | None, digits: int = 4) -> float | str:
    if value is None:
        return ""
    return round(value, digits)


def build_detail_rows(
    session_scores: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    labels_by_session = {row["session_id"]: row for row in labels}
    sessions_by_session = {row["session_id"]: row for row in sessions}

    detail_rows: list[dict[str, Any]] = []

    for score_row in session_scores:
        session_id = score_row.get("session_id")
        label_row = labels_by_session.get(session_id)
        session_row = sessions_by_session.get(session_id, {})
        if not label_row:
            continue

        score = parse_json_cell(score_row.get("session_score"))
        if not score:
            continue

        for trait, (pred_field, label_field) in TRAITS.items():
            pred = as_float(score.get(pred_field))
            label = as_float(label_row.get(label_field))
            if pred is None or label is None:
                continue

            detail_rows.append(
                {
                    "session_id": session_id,
                    "user_id": score_row.get("user_id"),
                    "trait": trait,
                    "pred": round(pred, 4),
                    "bfi": round(label, 4),
                    "error_pred_minus_bfi": round(pred - label, 4),
                    "abs_error": round(abs(pred - label), 4),
                    "aggregation_status": score_row.get("aggregation_status"),
                    "is_effective_session": session_row.get("is_effective_session"),
                    "is_complete_session": session_row.get("is_complete_session"),
                }
            )

    return detail_rows


def summarize(detail_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []

    groups = {
        "all": detail_rows,
        "clean": [
            row
            for row in detail_rows
            if truthy(row.get("is_effective_session"))
            and row.get("aggregation_status") == "ok"
        ],
    }

    for group_name, rows in groups.items():
        for trait in TRAITS:
            trait_rows = [row for row in rows if row["trait"] == trait]
            xs = [float(row["pred"]) for row in trait_rows]
            ys = [float(row["bfi"]) for row in trait_rows]
            errors = [float(row["error_pred_minus_bfi"]) for row in trait_rows]
            abs_errors = [float(row["abs_error"]) for row in trait_rows]

            summary_rows.append(
                {
                    "group": group_name,
                    "trait": trait,
                    "n": len(trait_rows),
                    "mae": round_or_blank(sum(abs_errors) / len(abs_errors) if abs_errors else None),
                    "mean_error_pred_minus_bfi": round_or_blank(
                        sum(errors) / len(errors) if errors else None
                    ),
                    "pearson": round_or_blank(pearson(xs, ys)),
                    "spearman": round_or_blank(spearman(xs, ys)),
                }
            )

    return summary_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate v0.4 session scores against BFI labels.")
    parser.add_argument("--session-scores", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--sessions", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    detail_rows = build_detail_rows(
        session_scores=read_csv(args.session_scores),
        labels=read_csv(args.labels),
        sessions=read_csv(args.sessions),
    )
    summary_rows = summarize(detail_rows)

    write_csv(args.output_dir / "v04_validation_detail.csv", detail_rows)
    write_csv(args.output_dir / "v04_validation_summary.csv", summary_rows)

    print(json.dumps(
        {
            "detail_count": len(detail_rows),
            "summary_count": len(summary_rows),
            "detail_path": str(args.output_dir / "v04_validation_detail.csv"),
            "summary_path": str(args.output_dir / "v04_validation_summary.csv"),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
