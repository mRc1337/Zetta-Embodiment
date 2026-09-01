from zetta.planner.codex import _planner_messages


def test_planner_messages_prefer_sdk_final_response() -> None:
    rendered = '[codex-system] turn/started\n[codex-reasoning] inspect\n[codex] {"ok": true}\n'

    assert _planner_messages(
        final_response='{"ok": true}', rendered_text=rendered
    ) == [{"role": "codex_sdk", "content": '{"ok": true}'}]


def test_planner_messages_fall_back_when_sdk_has_no_final_response() -> None:
    rendered = "legacy rendered response"

    assert _planner_messages(final_response=None, rendered_text=rendered) == [
        {"role": "codex_sdk", "content": rendered}
    ]
