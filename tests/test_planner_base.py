from zetta.planner.base import normalize_api_model_id


def test_normalize_api_model_id_adds_provider_for_frozen_bare_gpt_model() -> None:
    assert normalize_api_model_id("gpt-5.6-sol") == "openai-chat:gpt-5.6-sol"


def test_normalize_api_model_id_preserves_explicit_provider() -> None:
    assert (
        normalize_api_model_id("openai:gpt-5.6-sol")
        == "openai:gpt-5.6-sol"
    )
    assert (
        normalize_api_model_id("anthropic:claude-opus-4-8")
        == "anthropic:claude-opus-4-8"
    )
