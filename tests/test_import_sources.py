from __future__ import annotations

import json
import io
import multiprocessing
import threading
import zipfile
from pathlib import Path

from tools import import_sources
from tools.import_adapters.cleaning import clean_text_lines, validate_paragraphs
from tools.import_adapters import static_sites
from tools.import_adapters.registry import get_adapter, list_site_catalog
from tools.import_adapters.static_sites import RoyalRoadAdapter, Shu69Adapter


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _concurrent_document_import_worker(novels_dir, filename, chapter_num, ready, start, results):
    import_sources.NOVELS_DIR = Path(novels_dir)
    ready.put(filename)
    if not start.wait(15):
        results.put({"ok": False, "error": "start timeout"})
        return
    try:
        result = import_sources.import_document_bytes(
            slug="concurrent-novel",
            title="Concurrent Novel",
            filename=filename,
            raw=f"Chapter {chapter_num}\nBody for chapter {chapter_num}.".encode(),
            source_lang="en",
        )
        results.put({"ok": True, "imported": result["imported"]})
    except Exception as exc:
        results.put({"ok": False, "error": repr(exc)})


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


def test_split_paste_content_recognizes_common_novel_headings():
    content = "\n".join([
        "第1章 Arrival",
        "中文正文。",
        "第2話 Signal",
        "日本語の本文。",
        "제 3화 Return",
        "한국어 본문.",
        "Chapter 4 Home",
        "English body.",
    ])

    chapters = import_sources.split_paste_content(content)

    assert [chapter[0] for chapter in chapters] == [1, 2, 3, 4]
    assert [chapter[1] for chapter in chapters] == [
        "第1章 Arrival",
        "第2話 Signal",
        "제 3화 Return",
        "Chapter 4 Home",
    ]


def test_import_document_markdown_strips_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")
    raw = b"---\ntitle: shell metadata\n---\n\n# Chapter 1 - Start\n\nFirst paragraph.\n\nSecond paragraph.\n"

    result = import_sources.import_document_bytes(
        slug="markdown-novel",
        title="Markdown Novel",
        filename="book.md",
        raw=raw,
        source_lang="en",
    )

    saved = (tmp_path / "novels" / "markdown-novel" / "chapters" / "source" / "0001.md").read_text(encoding="utf-8")
    assert result["format"] == "markdown"
    assert result["encoding"] == "utf-8"
    assert result["chapterCount"] == 1
    assert "shell metadata" not in saved
    assert "# Chapter 1 - Start" in saved
    assert "Second paragraph." in saved


def test_import_document_html_ignores_shell_and_scripts(tmp_path, monkeypatch):
    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")
    raw = """
    <html><head><title>Fixture Book</title><style>.bad{display:block}</style></head>
    <body><nav>Home Library Account</nav><script>alert('noise')</script>
    <main><h1>Chapter 7 - Clean</h1><p>The first paragraph stays.</p>
    <p>The second paragraph stays.</p></main><footer>Copyright shell</footer></body></html>
    """.encode()

    result = import_sources.import_document_bytes(
        slug="html-novel",
        title="HTML Novel",
        filename="book.html",
        raw=raw,
        source_lang="en",
    )

    saved = (tmp_path / "novels" / "html-novel" / "chapters" / "source" / "0007.md").read_text(encoding="utf-8")
    assert result["format"] == "html"
    assert "The first paragraph stays." in saved
    assert "Home Library Account" not in saved
    assert "alert" not in saved
    assert "Copyright shell" not in saved


def test_import_document_html_preserves_article_header_chapter_heading(tmp_path, monkeypatch):
    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")
    raw = """
    <html><body>
      <header><h2>Site navigation</h2></header>
      <article>
        <header><h2>Chapter 12 - Inside Article</h2></header>
        <p>The chapter body remains readable.</p>
      </article>
      <footer>Site footer</footer>
    </body></html>
    """.encode()

    result = import_sources.import_document_bytes(
        slug="article-header-novel",
        title="Article Header Novel",
        filename="book.html",
        raw=raw,
        source_lang="en",
    )

    source_dir = tmp_path / "novels" / "article-header-novel" / "chapters" / "source"
    saved = (source_dir / "0012.md").read_text(encoding="utf-8")
    assert result["chapterCount"] == 1
    assert "# Chapter 12 - Inside Article" in saved
    assert "The chapter body remains readable." in saved
    assert "Site navigation" not in saved
    assert "Site footer" not in saved


def test_import_document_json_accepts_common_chapter_shapes(tmp_path, monkeypatch):
    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")
    raw = json.dumps({
        "title": "JSON Fixture",
        "chapters": [
            {"chapter": 2, "name": "Chapter 2 - Lists", "paragraphs": ["One.", "Two."]},
            {"index": 5, "title": "Chapter 5 - Body", "body": "Three.\n\nFour."},
        ],
    }).encode()

    result = import_sources.import_document_bytes(
        slug="json-novel",
        title="",
        filename="export.json",
        raw=raw,
        source_lang="en",
    )

    source_dir = tmp_path / "novels" / "json-novel" / "chapters" / "source"
    assert result["title"] == "JSON Fixture"
    assert result["chapterCount"] == 2
    assert (source_dir / "0002.md").exists()
    assert "Four." in (source_dir / "0005.md").read_text(encoding="utf-8")


def _fixture_epub() -> bytes:
    container = """<?xml version="1.0"?>
    <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
      <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
    </container>"""
    package = """<?xml version="1.0" encoding="UTF-8"?>
    <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
      <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>EPUB Fixture</dc:title></metadata>
      <manifest>
        <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
        <item id="c1" href="chapter-1.xhtml" media-type="application/xhtml+xml"/>
        <item id="c2" href="chapter-2.xhtml" media-type="application/xhtml+xml"/>
      </manifest>
      <spine><itemref idref="c1"/><itemref idref="c2"/></spine>
    </package>"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", package)
        archive.writestr("OEBPS/chapter-1.xhtml", "<html><head><title>Chapter 1 - Arrival</title></head><body><h1>Chapter 1 - Arrival</h1><p>First body.</p></body></html>")
        archive.writestr("OEBPS/chapter-2.xhtml", "<html><head><title>Chapter 2 - Signal</title></head><body><h1>Chapter 2 - Signal</h1><p>Second body.</p></body></html>")
    return output.getvalue()


def test_import_document_epub_uses_spine_order(tmp_path, monkeypatch):
    monkeypatch.setattr(import_sources, "NOVELS_DIR", tmp_path / "novels")

    result = import_sources.import_document_bytes(
        slug="epub-novel",
        title="",
        filename="book.epub",
        raw=_fixture_epub(),
        source_lang="en",
    )

    source_dir = tmp_path / "novels" / "epub-novel" / "chapters" / "source"
    assert result["format"] == "epub"
    assert result["encoding"] == "epub-xml"
    assert result["title"] == "EPUB Fixture"
    assert result["chapterCount"] == 2
    assert "First body." in (source_dir / "0001.md").read_text(encoding="utf-8")
    assert "Second body." in (source_dir / "0002.md").read_text(encoding="utf-8")


def test_document_decoder_handles_legacy_cjk_encodings():
    fixtures = [
        ("cn", "第1章 开始\n这是中文正文。", "gb18030"),
        ("jp", "第1話 はじまり\nこれは日本語の本文です。", "shift_jis"),
        ("kr", "제 1화 시작\n이것은 한국어 본문입니다.", "euc_kr"),
    ]

    for source_lang, original, encoding in fixtures:
        decoded, detected = import_sources.decode_document_bytes(original.encode(encoding), source_lang)
        assert decoded == original
        assert detected == encoding


def test_document_decoder_auto_selects_plausible_legacy_cjk_encoding():
    fixtures = [
        ("第1話 はじまり\nこれは日本語の本文です。", "shift_jis"),
        ("제 1화 시작\n이것은 한국어 본문입니다.", "euc_kr"),
    ]

    for original, encoding in fixtures:
        decoded, detected = import_sources.decode_document_bytes(original.encode(encoding), "auto")
        assert decoded == original
        assert detected == encoding


def test_split_paste_content_parses_chinese_numeral_headings():
    content = "\n".join([
        "第一章 初见",
        "这里是初见正文。",
        "第二章 重逢",
        "这里是重逢正文。",
        "第一万零二章 远行",
        "万章编号也应正确。",
    ])

    chapters = import_sources.split_paste_content(content)

    assert [chapter[0] for chapter in chapters] == [1, 2, 10_002]
    assert [chapter[1] for chapter in chapters] == ["第一章 初见", "第二章 重逢", "第一万零二章 远行"]


def test_import_document_rejects_unsupported_and_oversized_files():
    try:
        import_sources.parse_document_bytes(b"content", "book.pdf", "en")
    except ValueError as exc:
        assert "Unsupported document format" in str(exc)
    else:
        raise AssertionError("expected unsupported format error")

    try:
        import_sources.parse_document_bytes(
            b"x" * (import_sources.MAX_DOCUMENT_BYTES + 1),
            "book.txt",
            "en",
        )
    except ValueError as exc:
        assert "too large" in str(exc).lower()
    else:
        raise AssertionError("expected file size error")


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
