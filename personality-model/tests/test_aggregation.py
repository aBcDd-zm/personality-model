from src.aggregation import TRAIT_FIELDS, aggregate_scene_scores, aggregate_session_scores


def make_event(
    event_id,
    *,
    scene_id="SCENE_1",
    confidence=1.0,
    score=50,
    scored=True,
    is_valid_event=True,
    is_demo=False,
    is_low_quality=False,
    evidence=None,
):
    return {
        "event_id": event_id,
        "session_id": "S_1",
        "user_id": "U_1",
        "scene_id": scene_id,
        "scene_name": "Scene",
        "task_id": scene_id.replace("SCENE_", ""),
        "scored": scored,
        "is_valid_event": is_valid_event,
        "is_demo": is_demo,
        "is_low_quality": is_low_quality,
        "confidence": confidence,
        "evidence": evidence if evidence is not None else [{"quote": event_id}],
        "final_result": {"estimated_persona": {field: score for field in TRAIT_FIELDS}},
    }


def test_weighted_average_uses_confidence():
    rows = aggregate_scene_scores(
        [
            make_event("E1", confidence=0.2, score=10),
            make_event("E2", confidence=0.8, score=60),
        ]
    )

    assert rows[0]["scene_score"]["personality_openness"] == 50
    assert rows[0]["scene_confidence"] == 0.5
    assert rows[0]["aggregated_event_count"] == 2


def test_low_confidence_invalid_and_demo_events_do_not_aggregate():
    rows = aggregate_scene_scores(
        [
            make_event("E1", confidence=0.19, score=100),
            make_event("E2", is_valid_event=False, score=100),
            make_event("E3", is_demo=True, score=100),
            make_event("E4", is_low_quality=True, score=100),
            make_event("E5", confidence=0.5, score=20),
        ]
    )

    assert rows[0]["scene_score"]["personality_openness"] == 20
    assert rows[0]["event_count"] == 5
    assert rows[0]["aggregated_event_count"] == 1
    assert rows[0]["skipped_event_count"] == 4


def test_scene_and_session_output_fields_are_complete():
    events = [make_event("E1")]
    scene = aggregate_scene_scores(events)[0]
    session = aggregate_session_scores(events)[0]

    assert set(scene) == {
        "session_id",
        "user_id",
        "scene_id",
        "scene_name",
        "task_id",
        "event_count",
        "aggregated_event_count",
        "skipped_event_count",
        "scene_score",
        "scene_confidence",
        "evidence",
        "aggregation_status",
    }
    assert set(session) == {
        "session_id",
        "user_id",
        "event_count",
        "aggregated_event_count",
        "skipped_event_count",
        "scene_count",
        "session_score",
        "session_confidence",
        "evidence",
        "aggregation_status",
    }


def test_no_valid_events_returns_null_scores():
    rows = aggregate_session_scores([make_event("E1", confidence=0.1)])

    assert rows[0]["aggregation_status"] == "no_valid_events"
    assert rows[0]["session_confidence"] is None
    assert rows[0]["session_score"] == {field: None for field in TRAIT_FIELDS}


def test_evidence_is_deduped_and_limited():
    evidence = [{"quote": "same", "reason": "same"}]
    rows = aggregate_scene_scores(
        [
            make_event(f"E{i}", evidence=evidence)
            for i in range(12)
        ]
    )

    assert rows[0]["evidence"] == evidence
