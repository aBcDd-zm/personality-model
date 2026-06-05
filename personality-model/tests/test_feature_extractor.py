from src.feature_extractor import enrich_response_meta
from src.schemas import ResponseMeta


def test_response_length_is_computed():
    response = ResponseMeta(event_id="EV_001", user_free_text_input="我会负责确认风险")

    enriched = enrich_response_meta(response)

    assert enriched.response_length == len("我会负责确认风险")


def test_self_focus_ratio_is_computed():
    response = ResponseMeta(event_id="EV_001", user_free_text_input="我会先处理我的任务，再帮助团队")

    enriched = enrich_response_meta(response)

    assert enriched.response_self_focus_ratio > 0


def test_lexical_diversity_is_computed():
    response = ResponseMeta(event_id="EV_001", user_free_text_input="方案方案风险质量")

    enriched = enrich_response_meta(response)

    assert 0 < enriched.response_lexical_diversity <= 1


def test_empty_text_does_not_crash():
    response = ResponseMeta(event_id="EV_001", user_free_text_input=None)

    enriched = enrich_response_meta(response)

    assert enriched.response_length == 0
    assert enriched.response_self_focus_ratio == 0.0
    assert enriched.response_lexical_diversity == 0.0
    assert enriched.response_sentiment == 0.0

