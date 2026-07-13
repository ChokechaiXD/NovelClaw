import json

import pipeline
import pipeline_llm


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(
            {"choices": [{"message": {"content": "translated"}}]}
        ).encode("utf-8")


class _FakeLengthResponse(_FakeResponse):
    def read(self):
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {"content": "translated but incomplete"},
                        "finish_reason": "length",
                    }
                ],
                "usage": {"completion_tokens": 512},
            }
        ).encode("utf-8")


def test_call_llm_uses_overridden_provider_runtime_config(monkeypatch):
    calls = {"config": 0}
    limited = []

    def fake_provider_config():
        calls["config"] += 1
        return {
            "active": "alpha",
            "default_model": "default-model",
            "discovery_model": "judge-model",
            "providers": {
                "alpha": {
                    "base_url": "https://alpha.local/api/v1",
                    "api_key": "alpha-key",
                    "timeout_sec": 11,
                    "max_tokens": 111,
                    "temperature": 0.4,
                },
                "beta": {
                    "base_url": "https://beta.local/api/v1",
                    "api_key": "beta-key",
                    "timeout_sec": 22,
                    "max_tokens": 222,
                    "temperature": 0.2,
                },
            },
        }

    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["headers"] = dict(req.header_items())
        return _FakeResponse()

    monkeypatch.setattr(
        "llm_router.config_providers.get_provider_config",
        fake_provider_config,
    )
    monkeypatch.setattr(pipeline_llm, "_load_central_config", lambda: {})
    monkeypatch.setattr(pipeline_llm.urllib.request, "urlopen", fake_urlopen)

    class FakeLimit:
        def __init__(self, provider):
            self.provider = provider

        def __enter__(self):
            limited.append(self.provider)

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(pipeline_llm, "limit_llm_call", lambda provider: FakeLimit(provider))

    response, provider_name, model_name = pipeline_llm.call_llm("prompt", provider="beta", model="openrouter/test-model")

    assert response == "translated"
    assert pipeline.call_llm is pipeline_llm.call_llm
    assert provider_name == "beta"
    assert model_name == "openrouter/test-model"
    assert captured["url"] == "https://beta.local/api/v1/chat/completions"
    assert captured["timeout"] == 22
    assert captured["body"]["max_tokens"] == 222
    assert captured["body"]["temperature"] == 0.2
    assert captured["headers"]["Authorization"] == "Bearer beta-key"
    assert limited == ["beta"]
    assert calls["config"] == 1


def test_call_llm_accepts_provider_native_local_model_id(monkeypatch):
    captured = {}
    local_config = {
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key": "",
        "model": "qwen2.5:14b",
        "discovery_model": "qwen2.5:14b",
        "timeout": 30,
        "max_tokens": 512,
        "temperature": 0.2,
        "provider_name": "ollama",
    }

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse()

    class FakeLimit:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(pipeline_llm, "get_active_config", lambda _provider=None: dict(local_config))
    monkeypatch.setattr(pipeline_llm.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(pipeline_llm, "limit_llm_call", lambda _provider: FakeLimit())

    response, provider_name, model_name = pipeline_llm.call_llm("Translate", provider="ollama")

    assert response == "translated"
    assert provider_name == "ollama"
    assert model_name == "qwen2.5:14b"
    assert captured == {
        "url": "http://127.0.0.1:11434/v1/chat/completions",
        "body": {
            "model": "qwen2.5:14b",
            "messages": [{"role": "user", "content": "Translate"}],
            "max_tokens": 512,
            "temperature": 0.2,
        },
        "timeout": 30,
    }


def test_call_llm_rejects_missing_model_with_config_error(monkeypatch):
    monkeypatch.setattr(
        pipeline_llm,
        "get_active_config",
        lambda _provider=None: {
            "base_url": "http://127.0.0.1:11434/v1",
            "api_key": "",
            "model": "",
            "provider_name": "ollama",
        },
    )

    try:
        pipeline_llm.call_llm("Translate", provider="ollama")
    except ValueError as exc:
        assert str(exc) == "No model configured for provider 'ollama'."
    else:
        raise AssertionError("missing model must fail before making an HTTP request")


def test_call_llm_reports_finish_reason_without_changing_tuple_contract(monkeypatch):
    runtime_config = {
        "base_url": "http://127.0.0.1:11434/v1",
        "api_key": "",
        "model": "local-model",
        "discovery_model": "local-model",
        "timeout": 30,
        "max_tokens": 512,
        "temperature": 0.2,
        "provider_name": "local",
    }

    class FakeLimit:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(pipeline_llm, "get_active_config", lambda _provider=None: dict(runtime_config))
    monkeypatch.setattr(pipeline_llm.urllib.request, "urlopen", lambda *_args, **_kwargs: _FakeLengthResponse())
    monkeypatch.setattr(pipeline_llm, "limit_llm_call", lambda _provider: FakeLimit())
    metadata = {}

    response = pipeline_llm.call_llm("Translate", response_metadata=metadata)

    assert response == ("translated but incomplete", "local", "local-model")
    assert metadata == {"finish_reason": "length", "completion_tokens": 512}
