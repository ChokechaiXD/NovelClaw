from __future__ import annotations

import json
from pathlib import Path

from tools import import_sources
from tools.import_adapters.cleaning import clean_text_lines, validate_paragraphs
from tools.import_adapters import static_sites
from tools.import_adapters.registry import get_adapter, list_site_catalog
from tools.import_adapters.static_sites import RoyalRoadAdapter, Shu69Adapter


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


def test_royalroad_adapter_strips_source_watermark():
    adapter = RoyalRoadAdapter()
    ref = static_sites.ChapterRef(
        1,
        "Prologue - The End of Eternity",
        "https://www.royalroad.com/fiction/103742/example/chapter/1",
    )
    raw = """
    <html><body>
      <h1>Prologue - The End of Eternity</h1>
      <div class="chapter-inner">
        <p>The first true paragraph remained.</p>
        <p>This text was taken from Royal Road. Help the author by reading the original version there.</p>
        <p>The second true paragraph remained.</p>
      </div>
    </body></html>
    """

    chapter = adapter.extract(raw, ref)

    assert chapter.title == "Prologue - The End of Eternity"
    assert chapter.paragraphs == [
        "The first true paragraph remained.",
        "The second true paragraph remained.",
    ]


def test_cleaning_strips_chinese_site_shell_lines():
    real_a = "曹星緩緩睜開雙眼，輕聲感嘆道：“果然……兩條神性之間的沖突消失了。”" * 6
    real_b = "“雖然我現在還不知道，靠自己的力量解決這種沖突，需要耗費多大的代價。”" * 6
    paragraphs = clean_text_lines(
        "\n".join([
            "閱讀底色..",
            "淡藍海洋",
            "明黃清俊",
            "瀏覽記錄",
            "聯系我們:",
            "hjwzw@live.com",
            "隨機推薦：",
            "道君",
            "大王饒命",
            real_a,
            real_b,
        ])
    )
    warnings, needs_review = validate_paragraphs("第1章 Test", paragraphs)

    assert paragraphs == [
        real_a,
        real_b,
    ]
    assert not needs_review
    assert warnings == []


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


def test_site_catalog_exposes_stable_adapter_metadata():
    catalog = list_site_catalog()
    sites = catalog["sites"]
    by_id = {site["id"]: site for site in sites}

    assert {"69shu", "uukanshu", "syosetu", "kakuyomu", "royalroad"}.issubset(by_id)
    assert by_id["69shu"]["sourceLang"] == "cn"
    assert by_id["syosetu"]["sourceLang"] == "jp"
    assert by_id["royalroad"]["sourceLang"] == "en"
    assert by_id["69shu"]["capabilities"]["toc"] is True
    assert by_id["69shu"]["access"]["requiresJs"] is False
    assert catalog["fallbackAdapters"][0]["id"] == "manual-paste"
    assert any(item["id"] == "ocr" and item["status"] == "planned" for item in catalog["fallbackAdapters"])


def test_import_sites_command_returns_catalog_shape():
    payload = import_sources.import_sites()

    assert isinstance(payload["sites"], list)
    assert payload["sites"][0]["id"]
    assert "fallbackAdapters" in payload


def test_get_adapter_error_mentions_host_and_expected_domains():
    try:
        get_adapter("https://example.com/novel/1", "69shu")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert "example.com" in message
    assert "69shu.com" in message
    assert "auto" in message


def test_get_adapter_auto_error_mentions_manual_paste_path():
    try:
        get_adapter("https://example.com/novel/1", "auto")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected ValueError")

    assert "Unsupported source host" in message
    assert "manual paste" in message


def test_preview_url_includes_sample_chapter_diagnostics(monkeypatch):
    def fake_fetch(url, *_args, **_kwargs):
        if url.endswith("/1.html"):
            return read_fixture("import_69shu_chapter.html")
        return read_fixture("import_69shu_toc.html")

    monkeypatch.setattr(static_sites, "fetch_url", fake_fetch)
    adapter = Shu69Adapter()
    monkeypatch.setattr(import_sources, "get_adapter", lambda *_args, **_kwargs: adapter)
    monkeypatch.setattr(import_sources, "list_adapters", lambda: [adapter])

    payload = import_sources.preview_url("https://www.69shu.com/12345/", "69shu")

    assert payload["chapterCount"] == 2
    assert payload["diagnostics"]["hasToc"] is True
    assert payload["diagnostics"]["hasSampleContent"] is True
    assert payload["diagnostics"]["recommendImport"] is True
    assert payload["sampleChapter"]["num"] == 1
    assert payload["sampleChapter"]["paragraphCount"] >= 2


def test_import_url_writes_toc_manifest_for_later_repairs(tmp_path, monkeypatch):
    class FakeAdapter:
        id = "fake-site"
        display_name = "Fake Site"
        source_lang = "cn"

        def fetch_toc(self, url):
            return static_sites.TocResult(
                site=self.id,
                url=url,
                title="Fake Novel",
                author="Fixture Author",
                source_lang="cn",
                chapters=[
                    static_sites.ChapterRef(1, "第1章 Arrival", "https://fixture.test/1"),
                    static_sites.ChapterRef(2, "第2章 Signal", "https://fixture.test/2"),
                ],
            )

        def fetch_chapter(self, ref):
            return "<html><body><h1>{}</h1><div id='content'><p>正文一。</p><p>正文二。</p></div></body></html>".format(ref.title)

        def extract(self, raw, ref):
            return static_sites.ExtractedChapter(
                title=ref.title,
                paragraphs=["正文一。", "正文二。"],
                source_url=ref.url,
                source_lang="cn",
            )

    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")
    monkeypatch.setattr(import_sources, "get_adapter", lambda *_args, **_kwargs: FakeAdapter())

    result = import_sources.import_url("https://fixture.test/toc", "fake-novel", "fake-site")

    toc_path = tmp_path / "novels" / "fake-novel" / "chapters" / "source" / "toc.json"
    toc = json.loads(toc_path.read_text(encoding="utf-8"))

    assert result["tocPath"] == str(toc_path)
    assert toc["site"] == "fake-site"
    assert toc["chapterCount"] == 2
    assert toc["chapters"][1]["title"] == "第2章 Signal"


def test_recover_toc_uses_legacy_source_urls_without_writing_on_dry_run(tmp_path, monkeypatch):
    class FakeAdapter:
        id = "69shu"
        display_name = "Fake 69shu"
        source_lang = "cn"

        def fetch_toc(self, url):
            return static_sites.TocResult(
                site=self.id,
                url=url,
                title="Recovered Novel",
                source_lang="cn",
                chapters=[
                    static_sites.ChapterRef(1, "第1章 Recovered", "https://fixture.test/1"),
                ],
            )

    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")
    monkeypatch.setattr(import_sources, "get_adapter", lambda *_args, **_kwargs: FakeAdapter())
    novel_dir = tmp_path / "novels" / "legacy-novel"
    novel_dir.mkdir(parents=True)
    (novel_dir / "novel.json").write_text(json.dumps({
        "slug": "legacy-novel",
        "title": "Legacy Novel",
        "sourceUrls": {"69shu": "https://www.69shu.com/30190/"},
    }), encoding="utf-8")

    result = import_sources.recover_toc("legacy-novel", dry_run=True)
    toc_path = tmp_path / "novels" / "legacy-novel" / "chapters" / "source" / "toc.json"

    assert result["dryRun"] is True
    assert result["site"] == "69shu"
    assert result["chapterCount"] == 1
    assert result["sampleChapters"][0]["title"] == "第1章 Recovered"
    assert not toc_path.exists()


def test_recover_toc_apply_writes_manifest(tmp_path, monkeypatch):
    class FakeAdapter:
        id = "fixture"
        display_name = "Fixture"
        source_lang = "en"

        def fetch_toc(self, url):
            return static_sites.TocResult(
                site=self.id,
                url=url,
                title="Recovered Apply",
                source_lang="en",
                chapters=[
                    static_sites.ChapterRef(7, "Chapter 7 - Return", "https://fixture.test/7"),
                ],
            )

    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")
    monkeypatch.setattr(import_sources, "get_adapter", lambda *_args, **_kwargs: FakeAdapter())
    novel_dir = tmp_path / "novels" / "apply-novel"
    novel_dir.mkdir(parents=True)
    (novel_dir / "novel.json").write_text(json.dumps({
        "slug": "apply-novel",
        "title": "Apply Novel",
        "originalUrl": "https://fixture.test/toc",
        "sourceSite": "fixture",
    }), encoding="utf-8")

    result = import_sources.recover_toc("apply-novel", dry_run=False)
    toc_path = tmp_path / "novels" / "apply-novel" / "chapters" / "source" / "toc.json"
    toc = json.loads(toc_path.read_text(encoding="utf-8"))

    assert result["dryRun"] is False
    assert result["tocPath"] == str(toc_path)
    assert toc["chapters"][0]["num"] == 7
    assert toc["chapters"][0]["title"] == "Chapter 7 - Return"
