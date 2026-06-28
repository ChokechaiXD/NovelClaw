from llm_router import config_providers


def test_get_provider_config_caches_until_save(tmp_path, monkeypatch):
    config_path = tmp_path / "providers.yaml"
    config_path.write_text(
        "\n".join(
            [
                "active: alpha",
                'default_model: "model-alpha"',
                "providers: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_providers, "_CONFIG_PATH", config_path)
    getattr(config_providers, "clear_provider_config_cache", lambda: None)()

    first = config_providers.get_provider_config()
    config_path.write_text(
        "\n".join(
            [
                "active: beta",
                'default_model: "model-beta"',
                "providers: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    second = config_providers.get_provider_config()

    assert first["active"] == "alpha"
    assert second["active"] == "alpha"

    assert config_providers.save_provider_config(active="gamma") is True
    third = config_providers.get_provider_config()

    assert third["active"] == "gamma"


def test_save_provider_config_updates_discovery_model(tmp_path, monkeypatch):
    config_path = tmp_path / "providers.yaml"
    config_path.write_text(
        "\n".join(
            [
                "active: openmodel",
                'default_model: "deepseek-v4-flash"',
                'discovery_model: "old-discovery"',
                "providers: {}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_providers, "_CONFIG_PATH", config_path)

    saved = config_providers.save_provider_config(
        active="openrouter",
        default_model="google/gemma-4-26b-a4b-it:free",
        discovery_model="openai/gpt-oss-120b:free",
    )

    assert saved is True
    text = config_path.read_text(encoding="utf-8")
    assert "active: openrouter" in text
    assert 'default_model: "google/gemma-4-26b-a4b-it:free"' in text
    assert 'discovery_model: "openai/gpt-oss-120b:free"' in text
