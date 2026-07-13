"""Tests for llm_router config — core (config_providers) + admin (config_admin)."""

from llm_router import config_admin, config_providers


class _FakeModelResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"data":[{"id":"alpha/latest"},{"id":"beta-fast"}]}'


def _patch_config_path(monkeypatch, config_path):
    """Patch _CONFIG_PATH in both core and admin modules."""
    monkeypatch.setattr(config_providers, "_CONFIG_PATH", config_path)
    monkeypatch.setattr(config_admin, "_CONFIG_PATH", config_path)


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
    _patch_config_path(monkeypatch, config_path)
    # route novelclaw.config.yaml writes to the same tmp dir
    monkeypatch.setattr(config_admin, "_PROJECT_ROOT", tmp_path)
    config_providers.clear_provider_config_cache()

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

    assert config_admin.save_provider_config(active="gamma") is True
    third = config_providers.get_provider_config()

    # get_provider_config reads providers.yaml — cache clear picks up file change
    assert third["active"] == "beta"
    # but novelclaw.config.yaml now has the updated value
    central_text = (tmp_path / "novelclaw.config.yaml").read_text(encoding="utf-8")
    assert "provider: gamma" in central_text


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
    _patch_config_path(monkeypatch, config_path)
    monkeypatch.setattr(config_admin, "_PROJECT_ROOT", tmp_path)

    saved = config_admin.save_provider_config(
        active="openrouter",
        default_model="google/gemma-4-26b-a4b-it:free",
        discovery_model="openai/gpt-oss-120b:free",
    )

    assert saved is True
    central_text = (tmp_path / "novelclaw.config.yaml").read_text(encoding="utf-8")
    assert "provider: openrouter" in central_text
    assert "model: google/gemma-4-26b-a4b-it:free" in central_text
    assert "discovery_model: openai/gpt-oss-120b:free" in central_text
    # providers.yaml unchanged
    text = config_path.read_text(encoding="utf-8")
    assert "active: openmodel" in text
    assert 'discovery_model: "old-discovery"' in text


def test_save_provider_config_updates_custom_endpoint(tmp_path, monkeypatch):
    config_path = tmp_path / "providers.yaml"
    config_path.write_text(
        "\n".join(
            [
                "active: custom",
                'default_model: "custom-model"',
                "providers:",
                "  custom:",
                "    display_name: Custom",
                '    base_url: "http://localhost:8000/v1"',
                "    models:",
                '      - id: "custom-model"',
                '        name: "Custom model"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _patch_config_path(monkeypatch, config_path)
    config_providers.clear_provider_config_cache()

    saved = config_admin.save_provider_config(
        custom_base_url="http://127.0.0.1:1234/v1",
    )

    assert saved is True
    text = config_path.read_text(encoding="utf-8")
    assert 'base_url: "http://127.0.0.1:1234/v1"' in text


def test_save_provider_config_updates_local_provider_api_key(tmp_path, monkeypatch):
    config_path = tmp_path / "providers.yaml"
    config_path.write_text(
        "\n".join(
            [
                "active: openai",
                'default_model: "gpt-4o"',
                "providers:",
                "  openai:",
                "    display_name: OpenAI",
                '    base_url: "https://api.openai.com/v1"',
                "    api_key_env: OPENAI_API_KEY",
                '    api_key_file: ""',
                "    models:",
                '      - id: "gpt-4o"',
                '        name: "GPT-4o"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _patch_config_path(monkeypatch, config_path)
    monkeypatch.setattr(config_providers, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config_admin, "_PROJECT_ROOT", tmp_path)
    config_providers.clear_provider_config_cache()

    saved = config_admin.save_provider_config(
        api_key_provider="openai",
        api_key="«redacted:sk-…»",
    )

    assert saved is True
    assert '"openai_api_key": "«redacted:sk-…»"' in (tmp_path / "llm.json").read_text(encoding="utf-8")
    assert "«redacted:sk-…»" not in config_path.read_text(encoding="utf-8")
    config_providers.clear_provider_config_cache()
    cfg = config_providers.get_provider_config()
    assert cfg["providers"]["openai"]["api_key"] == "«redacted:sk-…»"


def test_get_providers_list_can_refresh_live_models(tmp_path, monkeypatch):
    config_path = tmp_path / "providers.yaml"
    config_path.write_text(
        "\n".join(
            [
                "active: alpha",
                'default_model: "static-model"',
                "providers:",
                "  alpha:",
                "    display_name: Alpha",
                '    base_url: "https://alpha.local/v1"',
                '    api_key: "secret"',
                "    models:",
                '      - id: "static-model"',
                '        name: "Static model"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(req.header_items())
        return _FakeModelResponse()

    _patch_config_path(monkeypatch, config_path)
    monkeypatch.setattr(config_admin.urllib.request, "urlopen", fake_urlopen)
    config_providers.clear_provider_config_cache()

    providers = config_admin.get_providers_list(refresh=True)

    assert providers[0]["model_source"] == "live"
    assert [model["id"] for model in providers[0]["models"]] == ["alpha/latest", "beta-fast"]
    assert captured["url"] == "https://alpha.local/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer secret"


def test_provider_config_resolves_root_placeholders_in_profiles(tmp_path, monkeypatch):
    config_path = tmp_path / "providers.yaml"
    config_path.write_text(
        "\n".join(
            [
                "active: openrouter",
                'default_model: "model-a"',
                'discovery_model: "judge-a"',
                "providers: {}",
                "profiles:",
                "  translate:",
                "    - provider: ${active}",
                "      model: ${default_model}",
                "  judge:",
                "    - provider: ${active}",
                "      model: ${discovery_model}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _patch_config_path(monkeypatch, config_path)
    config_providers.clear_provider_config_cache()

    cfg = config_providers.get_provider_config()

    assert cfg["profiles"]["translate"][0]["provider"] == "openrouter"
    assert cfg["profiles"]["translate"][0]["model"] == "model-a"
    assert cfg["profiles"]["judge"][0]["model"] == "judge-a"
