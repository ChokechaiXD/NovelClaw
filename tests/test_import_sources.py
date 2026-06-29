from __future__ import annotations

import json
from pathlib import Path

from tools import import_sources
from tools.import_adapters import static_sites
from tools.import_adapters.static_sites import Shu69Adapter


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_static_adapter_detects_and_parses_toc(monkeypatch):
    monkeypatch.setattr(static_sites, "fetch_url", lambda *_args, **_kwargs: read_fixture("import_69shu_toc.html"))

    adapter = Shu69Adapter()
    toc = adapter.fetch_toc("https://www.69shu.com/12345/")

    assert adapter.detect("https://www.69shu.com/12345/")
    assert toc.site == "69shu"
    assert toc.title == "Global Descent"
    assert [chapter.title for chapter in toc.chapters] == ["第1章 Arrival", "第2章 Signal"]
    assert toc.chapters[0].url == "https://www.69shu.com/12345/1.html"


def test_static_adapter_extracts_clean_chapter_text():
    adapter = Shu69Adapter()
    ref = static_sites.ChapterRef(1, "第1章 Arrival", "https://www.69shu.com/12345/1.html")

    chapter = adapter.extract(read_fixture("import_69shu_chapter.html"), ref)

    assert chapter.title == "第1章 Arrival"
    assert "\n".join(chapter.paragraphs) == read_fixture("import_expected_69shu.txt").strip()
    assert all("Advertisement" not in paragraph for paragraph in chapter.paragraphs)
    assert all("最新网址" not in paragraph for paragraph in chapter.paragraphs)


def test_import_paste_writes_canonical_source_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")

    result = import_sources.import_paste(
        slug="sample-novel",
        title="Sample Novel",
        source_lang="cn",
        content="第1章 Start\n第一段正文。\n第二段正文。",
        force=False,
    )

    source_path = tmp_path / "novels" / "sample-novel" / "chapters" / "source" / "0001.md"
    novel_json = tmp_path / "novels" / "sample-novel" / "novel.json"

    assert result["imported"] == 1
    assert source_path.exists()
    source_text = source_path.read_text(encoding="utf-8")
    assert "source_site: \"manual-paste\"" in source_text
    assert "# 第1章 Start" in source_text
    assert "第一段正文。" in source_text
    meta = json.loads(novel_json.read_text(encoding="utf-8"))
    assert meta["sourceLang"] == "cn"
    assert meta["sourceRefs"][0]["site"] == "manual-paste"


def test_parse_range_supports_commas_and_ranges():
    assert import_sources.parse_range("1,3-5") == {1, 3, 4, 5}
