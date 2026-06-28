import json

import pipeline


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(
            {"choices": [{"message": {"content": "translated"}}]}
        ).encode("utf-8")


def test_call_llm_uses_overridden_provider_runtime_config(monkeypatch):
    calls = {"config": 0}

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
    monkeypatch.setattr(pipeline.urllib.request, "urlopen", fake_urlopen)

    response, provider_name, model_name = pipeline.call_llm("prompt", provider="beta")

    assert response == "translated"
    assert provider_name == "beta"
    assert model_name == "default-model"
    assert captured["url"] == "https://beta.local/api/v1/chat/completions"
    assert captured["timeout"] == 22
    assert captured["body"]["max_tokens"] == 222
    assert captured["body"]["temperature"] == 0.2
    assert captured["headers"]["Authorization"] == "Bearer beta-key"
    assert calls["config"] == 1
