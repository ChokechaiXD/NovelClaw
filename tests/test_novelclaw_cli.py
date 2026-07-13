from __future__ import annotations

import json
import sys
import threading

import novelclaw
import pytest


def test_translate_json_parallel_forwards_mock_and_dry_run(monkeypatch, capsys):
    calls = []
    lock = threading.Lock()

    def fake_translate_one(**kwargs):
        with lock:
            calls.append(kwargs)
        return {
            "status": "ok",
            "ch": kwargs["ch_num"],
            "mock": kwargs["mock"],
            "dryRun": kwargs["dry_run"],
        }

    monkeypatch.setattr(novelclaw, "translate_one", fake_translate_one)

    novelclaw.cmd_translate(["1-2", "--json", "--parallel", "2", "--mock", "--dry-run"])

    assert sorted(call["ch_num"] for call in calls) == [1, 2]
    assert all(call["mock"] is True for call in calls)
    assert all(call["dry_run"] is True for call in calls)

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert sorted(line["ch"] for line in lines) == [1, 2]
    assert all(line["mock"] is True for line in lines)
    assert all(line["dryRun"] is True for line in lines)


def test_translate_batch_uses_default_parallel_workers(monkeypatch):
    captured = {}
    monkeypatch.setenv("NOVELCLAW_DEFAULT_PARALLEL", "4")

    def fake_parallel(ch_nums, parsed):
        captured["ch_nums"] = ch_nums
        captured["parallel"] = parsed.parallel
        captured["mock"] = parsed.mock

    monkeypatch.setattr(novelclaw, "_cmd_translate_parallel", fake_parallel)

    novelclaw.cmd_translate(["1-3", "--mock"])

    assert captured == {"ch_nums": [1, 2, 3], "parallel": 4, "mock": True}


def test_translate_sequential_overrides_default_parallel(monkeypatch, capsys):
    calls = []
    monkeypatch.setenv("NOVELCLAW_DEFAULT_PARALLEL", "4")
    monkeypatch.setattr(
        novelclaw,
        "_cmd_translate_parallel",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("parallel should not run")),
    )

    def fake_translate_one(**kwargs):
        calls.append(kwargs["ch_num"])
        return {"status": "dry_run", "ch": kwargs["ch_num"]}

    monkeypatch.setattr(novelclaw, "translate_one", fake_translate_one)

    novelclaw.cmd_translate(["1-2", "--json", "--sequential", "--mock", "--dry-run"])

    assert calls == [1, 2]
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert [line["ch"] for line in lines] == [1, 2]


def test_translate_parallel_retries_failed_chapters(monkeypatch):
    attempts: dict[int, int] = {}

    def fake_translate_one(**kwargs):
        ch = kwargs["ch_num"]
        attempts[ch] = attempts.get(ch, 0) + 1
        if ch == 1 and attempts[ch] == 1:
            return {"status": "failed", "ch": ch, "reason": "provider busy"}
        return {"status": "ok", "ch": ch, "paragraphs": 1, "score": 90}

    monkeypatch.setattr(novelclaw, "translate_one", fake_translate_one)

    novelclaw.cmd_translate(["1-2", "--parallel", "2", "--retry", "1"])

    assert attempts == {1: 2, 2: 1}



def test_import_sites_loads_active_importer(capsys):
    try:
        novelclaw.cmd_import_sites([])
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    assert '"sites"' in output
    assert '69shu' in output


def test_removed_scrape_command_is_not_advertised(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["novelclaw.py", "scrape"])

    with pytest.raises(SystemExit) as exc:
        novelclaw.main()

    output = capsys.readouterr().out
    assert exc.value.code == 1
    assert "ไม่รู้จักคำสั่ง 'scrape'" in output
    assert "config, import-url" in output
    assert "config, scrape" not in output



def test_save_runtime_config_updates_model_used_by_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(novelclaw, "_PROJECT_ROOT", tmp_path)
    (tmp_path / "novelclaw.config.yaml").write_text(
        "provider: custom\nmodel: old-model\ndiscovery_model: old-discovery\n",
        encoding="utf-8",
    )

    novelclaw._save_runtime_config(model="new-model", discovery_model="new-discovery")

    saved = (tmp_path / "novelclaw.config.yaml").read_text(encoding="utf-8")
    assert "model: new-model" in saved
    assert "discovery_model: new-discovery" in saved
    assert "provider: custom" in saved
