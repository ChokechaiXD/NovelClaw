import json

from atomic_io import atomic_write_json, atomic_write_text


def test_atomic_write_text_replaces_existing_file(tmp_path):
    target = tmp_path / "config.txt"
    target.write_text("old", encoding="utf-8")

    atomic_write_text(target, "new")

    assert target.read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob("tmp*"))


def test_atomic_write_json_writes_valid_json_with_newline(tmp_path):
    target = tmp_path / "data.json"

    atomic_write_json(target, {"terms": [{"source": "BUFF", "thai": "บัฟ"}]})

    raw = target.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert json.loads(raw)["terms"][0]["thai"] == "บัฟ"
