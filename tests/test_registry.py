"""test_registry.py — Multi-novel registry (Phase 2 — 2026-06-14).

Locks down:
  - parse_frontmatter() — YAML frontmatter extraction
  - novel_meta() — single novel metadata
  - list_novels() — scan all novels/
  - get_novel() — single novel by slug
  - get_default_novel() — first novel (backward compat)
  - _count_translated() — chapter count logic
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Make tools/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

import pytest  # noqa: E402

import registry as reg  # noqa: E402


# ── parse_frontmatter ───────────────────────────────────────────────

class TestParseFrontmatter:
    """Extract YAML frontmatter from markdown content."""

    def test_with_frontmatter(self):
        text = '---\nslug: foo\ntitle: Foo\n---\n\n# Body'
        meta, body = reg.parse_frontmatter(text)
        assert meta == {'slug': 'foo', 'title': 'Foo'}
        assert body.strip() == '# Body'

    def test_without_frontmatter(self):
        text = '# Just markdown\n\nNo frontmatter here.'
        meta, body = reg.parse_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_quoted_values(self):
        text = "---\ntitle: 'Quoted Title'\nauthor: \"Quoted Author\"\n---\n"
        meta, _ = reg.parse_frontmatter(text)
        assert meta['title'] == 'Quoted Title'
        assert meta['author'] == 'Quoted Author'

    def test_int_values(self):
        text = '---\ntotal_chapters: 1239\nstatus_count: 42\n---\n'
        meta, _ = reg.parse_frontmatter(text)
        assert meta['total_chapters'] == 1239
        assert meta['status_count'] == 42

    def test_multiline_body_preserved(self):
        text = '---\nslug: foo\n---\n\n# Title\n\nParagraph 1\n\nParagraph 2\n'
        meta, body = reg.parse_frontmatter(text)
        assert meta == {'slug': 'foo'}
        assert 'Paragraph 1' in body
        assert 'Paragraph 2' in body

    def test_empty_frontmatter(self):
        text = '---\n---\n\nbody'
        meta, body = reg.parse_frontmatter(text)
        assert meta == {}
        assert body.strip() == 'body'

    def test_comments_in_frontmatter(self):
        text = '---\n# this is a comment\nslug: foo\n---\n'
        meta, _ = reg.parse_frontmatter(text)
        assert meta == {'slug': 'foo'}

    def test_blank_lines_around_body(self):
        text = '---\nslug: foo\n---\n\n\n\nbody text\n'
        _, body = reg.parse_frontmatter(text)
        assert 'body text' in body


# ── novel_meta + list_novels ────────────────────────────────────────

class TestNovelMeta:
    """Read metadata for one novel."""

    def test_existing_novel(self):
        meta = reg.novel_meta('global-descent')
        assert meta is not None
        assert meta['slug'] == 'global-descent'
        # Has the new frontmatter fields
        assert meta['title']  # non-empty
        assert meta['source_lang'] == 'cn'
        assert meta['target_lang'] == 'th'
        assert meta['total_chapters'] == 1239

    def test_nonexistent_novel(self):
        assert reg.novel_meta('does-not-exist') is None

    def test_includes_paths(self):
        meta = reg.novel_meta('global-descent')
        assert meta['chapters_dir'].name == 'chapters'
        assert meta['glossary_dir'].name == 'glossary'
        assert meta['source_dir'].name == 'source'
        assert meta['meta_path'].name == 'meta.md'

    def test_includes_translated_count(self):
        meta = reg.novel_meta('global-descent')
        assert 'translated' in meta
        assert meta['translated'] >= 52  # we have 52 .json

    def test_fake_novel_dir_no_meta(self, monkeypatch):
        """Dir without meta.md is not a novel."""
        d = Path(tempfile.mkdtemp(prefix="reg_fake_"))
        try:
            fake = d / 'fake-novel'
            fake.mkdir()
            monkeypatch.setattr(reg, 'NOVELS_DIR', d)
            assert reg.novel_meta('fake-novel') is None
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestListNovels:
    """List all novels in the directory."""

    def test_returns_list(self):
        novels = reg.list_novels()
        assert isinstance(novels, list)

    def test_includes_global_descent(self):
        novels = reg.list_novels()
        slugs = [n['slug'] for n in novels]
        assert 'global-descent' in slugs

    def test_sorted_by_slug(self):
        novels = reg.list_novels()
        slugs = [n['slug'] for n in novels]
        assert slugs == sorted(slugs)

    def test_skips_non_novel_dirs(self, monkeypatch):
        """Dirs without meta.md are skipped."""
        d = Path(tempfile.mkdtemp(prefix="reg_list_"))
        try:
            # Create valid novel
            valid = d / 'valid-novel'
            valid.mkdir()
            (valid / 'meta.md').write_text('---\nslug: valid-novel\n---\n', encoding='utf-8')
            # Create invalid (no meta.md)
            invalid = d / 'not-a-novel'
            invalid.mkdir()
            monkeypatch.setattr(reg, 'NOVELS_DIR', d)
            novels = reg.list_novels()
            slugs = [n['slug'] for n in novels]
            assert 'valid-novel' in slugs
            assert 'not-a-novel' not in slugs
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestGetNovel:
    """Get one novel by slug."""

    def test_get_existing(self):
        novel = reg.get_novel('global-descent')
        assert novel is not None
        assert novel['slug'] == 'global-descent'

    def test_get_nonexistent(self):
        assert reg.get_novel('does-not-exist') is None


class TestGetDefaultNovel:
    """Backwards compat — tools that don't specify a novel."""

    def test_prefers_global_descent(self):
        novel = reg.get_default_novel()
        # global-descent exists, should be the default
        assert novel is not None
        assert novel['slug'] == 'global-descent'

    def test_falls_back_to_first_alphabetically(self, monkeypatch):
        """If global-descent doesn't exist, pick first alphabetically."""
        d = Path(tempfile.mkdtemp(prefix="reg_default_"))
        try:
            # Create 2 novels, no global-descent
            for slug in ('alpha-novel', 'beta-novel'):
                p = d / slug
                p.mkdir()
                (p / 'meta.md').write_text(f'---\nslug: {slug}\n---\n', encoding='utf-8')
            monkeypatch.setattr(reg, 'NOVELS_DIR', d)
            novel = reg.get_default_novel()
            # alpha-novel is first alphabetically
            assert novel['slug'] == 'alpha-novel'
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ── _count_translated ──────────────────────────────────────────────

class TestCountTranslated:
    """Count translated chapter files (json + legacy md)."""

    def test_count_json_only(self, monkeypatch):
        d = Path(tempfile.mkdtemp(prefix="reg_count_"))
        try:
            novel_dir = d / 'test'
            novel_dir.mkdir()
            chapters = novel_dir / 'chapters'
            chapters.mkdir()
            for i in [1, 5, 10]:
                (chapters / f'{i:04d}.json').write_text('{}', encoding='utf-8')
            (novel_dir / 'meta.md').write_text('---\nslug: test\n---\n', encoding='utf-8')
            monkeypatch.setattr(reg, 'NOVELS_DIR', d)
            meta = reg.novel_meta('test')
            assert meta is not None
            assert meta['translated'] == 3
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_count_json_and_md(self, monkeypatch):
        """Both .json and .md count, with .json preferred for same number."""
        d = Path(tempfile.mkdtemp(prefix="reg_count2_"))
        try:
            novel_dir = d / 'test'
            novel_dir.mkdir()
            chapters = novel_dir / 'chapters'
            chapters.mkdir()
            # ch 1: .json only
            (chapters / '0001.json').write_text('{}', encoding='utf-8')
            # ch 2: .md only (legacy)
            (chapters / '0002.md').write_text('body', encoding='utf-8')
            # ch 3: BOTH .json and .md — counts as 1
            (chapters / '0003.json').write_text('{}', encoding='utf-8')
            (chapters / '0003.md').write_text('body', encoding='utf-8')
            # ch 4: .md only
            (chapters / '0004.md').write_text('body', encoding='utf-8')
            # Non-chapter file (audit.md) should not count
            (chapters / 'audit.md').write_text('audit', encoding='utf-8')
            # Subdir (audit folder) should not count
            (chapters / '0001').mkdir()
            (chapters / '0001' / 'audit.md').write_text('audit', encoding='utf-8')
            (novel_dir / 'meta.md').write_text('---\nslug: test\n---\n', encoding='utf-8')
            monkeypatch.setattr(reg, 'NOVELS_DIR', d)
            meta = reg.novel_meta('test')
            assert meta is not None
            # 1, 2, 3, 4 = 4 chapters
            assert meta['translated'] == 4
        finally:
            shutil.rmtree(d, ignore_errors=True)


# ── CLI ──────────────────────────────────────────────────────────────

class TestCLI:
    """Command-line interface prints novel info."""

    def test_main_runs(self, capsys):
        reg.main()
        captured = capsys.readouterr()
        assert 'global-descent' in captured.out
        assert 'cn -> th' in captured.out
