from src.aggregation import TRAIT_FIELDS
from src.profile_updater import initial_profile, update_profile


def test_initial_profile_sets_all_traits_to_50():
    assert initial_profile() == {field: 50.0 for field in TRAIT_FIELDS}


def test_update_profile_uses_default_alpha():
    old_profile = {field: 50 for field in TRAIT_FIELDS}
    session_score = {field: 100 for field in TRAIT_FIELDS}

    assert update_profile(old_profile, session_score)["personality_openness"] == 60.0


def test_none_session_score_keeps_old_dimension():
    old_profile = {field: 40 for field in TRAIT_FIELDS}
    session_score = {field: 80 for field in TRAIT_FIELDS}
    session_score["personality_neuroticism"] = None

    updated = update_profile(old_profile, session_score)

    assert updated["personality_openness"] == 48.0
    assert updated["personality_neuroticism"] == 40.0


def test_update_profile_rounds_to_two_decimals():
    old_profile = {field: 33.333 for field in TRAIT_FIELDS}
    session_score = {field: 66.666 for field in TRAIT_FIELDS}

    assert update_profile(old_profile, session_score, alpha=0.2)["personality_openness"] == 40.0
