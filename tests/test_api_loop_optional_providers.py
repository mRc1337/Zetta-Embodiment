from __future__ import annotations

import builtins

import pytest

pydantic_ai = pytest.importorskip("pydantic_ai")
ModelSettings = pydantic_ai.ModelSettings

from zetta.planner.api_loop import _build_model_settings
from zetta.planner.provider_proxy import BROKER_URL_ENV


class _OpenAIOnlyModel:
    pass


class OpenAIResponsesModel:
    pass


OpenAIResponsesModel.__module__ = "pydantic_ai.models.openai"


def test_openai_model_settings_do_not_import_anthropic(monkeypatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("pydantic_ai.models.anthropic"):
            raise AssertionError("OpenAI-compatible models must not import Anthropic")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    settings = _build_model_settings(_OpenAIOnlyModel(), max_tokens=4096)

    # ModelSettings is a TypedDict and deliberately has no runtime
    # ``isinstance`` support; compare the returned structure instead.
    assert settings == ModelSettings(max_tokens=4096)


def test_brokered_responses_disable_provider_owned_reasoning_ids(
    monkeypatch,
) -> None:
    monkeypatch.setenv(BROKER_URL_ENV, "http://127.0.0.1:4110")

    settings = _build_model_settings(OpenAIResponsesModel(), max_tokens=4096)

    assert settings == ModelSettings(
        max_tokens=4096,
        openai_send_reasoning_ids=False,
        openai_reasoning_context="current_turn",
    )
