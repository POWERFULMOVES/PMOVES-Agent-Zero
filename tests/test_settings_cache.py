import copy

from helpers import extension, settings


def test_settings_snapshot_is_limited_to_one_prompt(monkeypatch):
    configured = settings.get_default_settings()
    configured["api_keys"] = {"provider": "secret"}
    versions = iter(["first", "second", "third", "fourth"])
    calls = 0

    def defaults():
        nonlocal calls
        calls += 1
        result = copy.deepcopy(configured)
        result["version"] = next(versions)
        return result

    monkeypatch.setattr(settings, "_settings", configured)
    monkeypatch.setattr(settings, "_read_settings_file", lambda: configured)
    monkeypatch.setattr(settings, "get_default_settings", defaults)
    monkeypatch.setattr(settings, "_load_sensitive_settings", lambda _value: None)

    token = settings.begin_prompt_settings_snapshot()
    try:
        configured["workdir_show"] = False
        first = settings.get_settings_for_prompt()
        second = settings.get_settings_for_prompt()

        assert calls == 1
        assert first == second
        assert first["workdir_show"] is True
        assert first is not second
        assert first["api_keys"] is not second["api_keys"]

        first["api_keys"]["provider"] = "masked"
        assert settings.get_settings_for_prompt()["api_keys"]["provider"] == "secret"

        current = settings.get_settings()
        assert current["version"] == "second"
        assert current["workdir_show"] is False
        assert settings.get_settings_for_prompt()["workdir_show"] is True

        reloaded = settings.reload_settings()
        assert reloaded["version"] == "third"
        assert reloaded["workdir_show"] is False
        assert settings.get_settings_for_prompt() == reloaded
    finally:
        settings.end_prompt_settings_snapshot(token)

    refreshed = settings.get_settings()
    assert refreshed["workdir_show"] is False
    assert refreshed["version"] == "fourth"
    assert calls == 4


def test_prompt_snapshot_hooks_are_registered_and_paired():
    start = next(
        cls
        for cls in extension._get_extension_classes(  # type: ignore[attr-defined]
            "_functions/agent/Agent/prepare_prompt/start"
        )
        if cls.__name__ == "SnapshotPromptSettings"
    )
    end = next(
        cls
        for cls in extension._get_extension_classes(  # type: ignore[attr-defined]
            "_functions/agent/Agent/prepare_prompt/end"
        )
        if cls.__name__ == "RestorePromptSettings"
    )
    previous = settings._prompt_settings_snapshot.get()
    data = {}

    start(agent=None).execute(data=data)
    try:
        assert settings._prompt_settings_snapshot.get() is not None
    finally:
        end(agent=None).execute(data=data)

    assert settings._prompt_settings_snapshot.get() is previous
