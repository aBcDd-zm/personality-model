"""Adapters that normalize external event payloads into ScoreInput."""

from .v04_event_adapter import build_score_input_from_v04_event

__all__ = ["build_score_input_from_v04_event"]
