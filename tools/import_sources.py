"""NovelClaw source import engine.

Core flow:
    Source Adapter -> Extract -> Clean -> Validate -> Save

OCR/image/PDF imports are intentionally not part of this core path. They can be
added later as adapters that return the same extracted chapter shape.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from import_adapters import get_adapter, list_adapters
    from import_adapters.base import ChapterRef, ExtractedChapter
    from import_adapters.cleaning import clean_text_lines, validate_paragraphs
    from import_adapters.registry import list_site_catalog
except ModuleNotFoundError:
    from tools.import_adapters import get_adapter, list_adapters
    from tools.import_adapters.base import ChapterRef, ExtractedChapter
    from tools.import_adapters.cleaning import clean_text_lines, validate_paragraphs
    from tools.import_adapters.registry import list_site_catalog

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOVELS_DIR = PROJECT_ROOT / "novels"
SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def parse_range(range_text: str | None) -> set[int] | None:
    if not range_text:
        return None
    selected: set[int] = set()
    for part in range_text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = [int(x.strip()) for x in part.split("-", 1)]
            if b < a:
                raise ValueError("range end must be greater than or equal to start")
            selected.update(range(a, b + 1))
        else:
            selected.add(int(part))
    return selected


def assert_slug(slug: str) -> None:
    if not slug or not SLUG_RE.match(slug):
        raise ValueError("Invalid slug format")


def source_dir(slug: str) -> Path:
    assert_slug(slug)
    path = NOVELS_DIR / slug / "chapters" / "source"
    path.mkdir(parents=True, exist_ok=True)
    return path


def source_path(slug: str, num: int) -> Path:
    return source_dir(slug) / f"{num:04d}.md"


def source_toc_path(slug: str) -> Path:
    return source_dir(slug) / "toc.json"


def source_toc_path_no_create(slug: str) -> Path:
    assert_slug(slug)
    return NOVELS_DIR / slug / "chapters" / "source" / "toc.json"


def frontmatter_value(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def render_source_markdown(chapter: ExtractedChapter, site: str, import_warnings: list[str]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    header = [
        "---",
        f"source_url: {frontmatter_value(chapter.source_url)}",
        f"source_site: {frontmatter_value(site)}",
        f"source_lang: {frontmatter_value(chapter.source_lang)}",
        f"imported_at: {frontmatter_value(now)}",
        f"needs_review: {'true' if chapter.needs_review else 'false'}",
        f"import_warnings: {json.dumps(import_warnings, ensure_ascii=False)}",
        "---",
    ]
    body = [f"# {chapter.title.strip() or 'Untitled'}"]
    body.extend(p.strip() for p in chapter.paragraphs if p.strip())
    return "\n".join(header) + "\n\n" + "\n\n".join(body).rstrip() + "\n"


def update_novel_json(
    slug: str,
    *,
    title: str,
    author: str = "",
    source_lang: str = "cn",
    source_site: str = "",
    source_url: str = "",
    total_chapters: int = 0,
) -> dict:
    assert_slug(slug)
    novel_dir = NOVELS_DIR / slug
    novel_dir.mkdir(parents=True, exist_ok=True)
    path = novel_dir / "novel.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        data = {}

    refs = data.get("sourceRefs")
    if not isinstance(refs, list):
        refs = []
    if source_url and not any(ref.get("url") == source_url for ref in refs if isinstance(ref, dict)):
        refs.append({"site": source_site, "url": source_url, "importedAt": datetime.now(timezone.utc).isoformat()})

    data.update(
        {
            "slug": slug,
            "title": data.get("title") or title or slug,
            "translatedTitle": data.get("translatedTitle", ""),
            "author": data.get("author") or author or "",
            "sourceLang": source_lang or data.get("sourceLang") or data.get("source_lang") or "cn",
            "targetLang": data.get("targetLang") or data.get("target_lang") or "th",
            "status": data.get("status") or "ongoing",
            "totalChapters": max(int(data.get("totalChapters") or 0), int(total_chapters or 0)),
            "description": data.get("description", ""),
            "originalUrl": data.get("originalUrl") or source_url,
            "sourceSite": data.get("sourceSite") or source_site,
            "sourceRefs": refs,
            "lastImportedAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def write_toc_manifest(slug: str, toc, adapter_id: str) -> Path:
    payload = {
        "site": adapter_id,
        "url": toc.url,
        "title": toc.title,
        "author": toc.author,
        "sourceLang": toc.source_lang,
        "chapterCount": len(toc.chapters),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "chapters": [asdict(ch) for ch in toc.chapters],
    }
    path = source_toc_path(slug)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_novel_json(slug: str) -> dict:
    assert_slug(slug)
    path = NOVELS_DIR / slug / "novel.json"
    if not path.exists():
        raise ValueError(f"novel.json not found for slug: {slug}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid novel.json for {slug}: {exc}") from exc


def infer_toc_source(slug: str, url: str | None = None, site: str = "auto") -> tuple[str, str]:
    if url:
        return url, site or "auto"

    meta = read_novel_json(slug)
    source_urls = meta.get("sourceUrls")
    if isinstance(source_urls, dict):
        for key, value in source_urls.items():
            if value and str(value).startswith(("http://", "https://")):
                return str(value), key if site == "auto" else site

    refs = meta.get("sourceRefs")
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            ref_url = str(ref.get("url") or "")
            if ref_url.startswith(("http://", "https://")):
                ref_site = str(ref.get("site") or "auto")
                return ref_url, ref_site if site == "auto" else site

    original_url = str(meta.get("originalUrl") or "")
    if original_url.startswith(("http://", "https://")):
        source_site = str(meta.get("sourceSite") or "auto")
        return original_url, source_site if site == "auto" else site

    raise ValueError("No recoverable TOC URL found in novel.json")


def recover_toc(slug: str, site: str = "auto", url: str | None = None, dry_run: bool = True) -> dict:
    assert_slug(slug)
    toc_url, toc_site = infer_toc_source(slug, url, site)
    adapter = get_adapter(toc_url, toc_site)
    toc = adapter.fetch_toc(toc_url)
    toc_path = source_toc_path_no_create(slug)
    if not dry_run:
        toc_path = write_toc_manifest(slug, toc, adapter.id)
    return {
        "slug": slug,
        "dryRun": dry_run,
        "site": adapter.id,
        "url": toc_url,
        "title": toc.title,
        "sourceLang": toc.source_lang,
        "chapterCount": len(toc.chapters),
        "tocPath": str(toc_path),
        "sampleChapters": [asdict(ch) for ch in toc.chapters[:20]],
    }


def preview_url(url: str, site: str = "auto") -> dict:
    adapter = get_adapter(url, site)
    toc = adapter.fetch_toc(url)
    sample: dict | None = None
    diagnostics: dict = {
        "hasToc": len(toc.chapters) > 0,
        "hasSampleContent": False,
        "recommendImport": len(toc.chapters) > 0,
        "warnings": [],
    }
    if toc.chapters:
        ref = toc.chapters[0]
        try:
            raw = adapter.fetch_chapter(ref)
            chapter = adapter.extract(raw, ref)
            total_chars = sum(len(p) for p in chapter.paragraphs)
            sample = {
                "num": ref.num,
                "title": chapter.title or ref.title,
                "sourceUrl": chapter.source_url,
                "paragraphCount": len(chapter.paragraphs),
                "charCount": total_chars,
                "paragraphs": chapter.paragraphs[:3],
                "warnings": list(chapter.warnings),
                "needsReview": chapter.needs_review,
            }
            diagnostics["hasSampleContent"] = total_chars > 0 and len(chapter.paragraphs) > 0
            diagnostics["warnings"] = list(chapter.warnings)
            diagnostics["recommendImport"] = diagnostics["hasSampleContent"] and "empty_content" not in chapter.warnings
        except Exception as exc:
            diagnostics["sampleError"] = str(exc)[:200]
            diagnostics["recommendImport"] = False
    return {
        "site": toc.site,
        "displayName": getattr(adapter, "display_name", toc.site),
        "url": toc.url,
        "title": toc.title,
        "author": toc.author,
        "sourceLang": toc.source_lang,
        "chapterCount": len(toc.chapters),
        "chapters": [asdict(ch) for ch in toc.chapters[:200]],
        "sampleChapter": sample,
        "diagnostics": diagnostics,
        "supportedAdapters": [adapter.id for adapter in list_adapters()],
    }


def import_sites() -> dict:
    return list_site_catalog()


def import_url(url: str, slug: str, site: str = "auto", range_text: str | None = None, force: bool = False) -> dict:
    assert_slug(slug)
    adapter = get_adapter(url, site)
    toc = adapter.fetch_toc(url)
    selected = parse_range(range_text)
    chapters = [ch for ch in toc.chapters if selected is None or ch.num in selected]
    if not chapters:
        raise ValueError("No chapters matched the requested import range")

    results: list[dict] = []
    imported = skipped = failed = 0
    for ref in chapters:
        out_path = source_path(slug, ref.num)
        if out_path.exists() and not force:
            skipped += 1
            results.append({"status": "skipped", "num": ref.num, "title": ref.title, "path": str(out_path)})
            continue
        try:
            raw = adapter.fetch_chapter(ref)
            chapter = adapter.extract(raw, ref)
            warnings = list(chapter.warnings)
            out_path.write_text(render_source_markdown(chapter, adapter.id, warnings), encoding="utf-8")
            imported += 1
            results.append(
                {
                    "status": "imported",
                    "num": ref.num,
                    "title": chapter.title,
                    "path": str(out_path),
                    "warnings": warnings,
                    "needsReview": chapter.needs_review,
                }
            )
        except Exception as exc:
            failed += 1
            results.append({"status": "failed", "num": ref.num, "title": ref.title, "reason": str(exc)[:200]})

    update_novel_json(
        slug,
        title=toc.title,
        author=toc.author,
        source_lang=toc.source_lang,
        source_site=adapter.id,
        source_url=url,
        total_chapters=len(toc.chapters),
    )
    toc_path = write_toc_manifest(slug, toc, adapter.id)
    return {
        "slug": slug,
        "site": adapter.id,
        "title": toc.title,
        "sourceLang": toc.source_lang,
        "chapterCount": len(toc.chapters),
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "tocPath": str(toc_path),
        "results": results,
    }


def split_paste_content(content: str, split_rule: str | None = None) -> list[tuple[int, str, list[str]]]:
    rule = split_rule or r"(?:ตอนที่|第|Chapter)\s*(\d+)\s*(?:章|ตอน)?"
    regex = re.compile(rf"^\s*({rule}.*?)\s*$", re.MULTILINE | re.IGNORECASE)
    matches = list(regex.finditer(content))
    if not matches:
        paragraphs = clean_text_lines(content)
        return [(1, "Chapter 1", paragraphs)]

    chapters: list[tuple[int, str, list[str]]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        title = match.group(1).strip()
        num_match = re.search(r"\d+", title)
        num = int(num_match.group(0)) if num_match else idx + 1
        paragraphs = clean_text_lines(content[start:end])
        if not paragraphs:
            paragraphs = [title]
        chapters.append((num, title, paragraphs))
    return chapters


def import_paste(
    *,
    slug: str,
    title: str,
    content: str,
    source_lang: str = "cn",
    author: str = "",
    split_rule: str | None = None,
    force: bool = False,
) -> dict:
    assert_slug(slug)
    chunks = split_paste_content(content, split_rule)
    results: list[dict] = []
    imported = skipped = 0
    for num, chapter_title, paragraphs in chunks:
        out_path = source_path(slug, num)
        if out_path.exists() and not force:
            skipped += 1
            results.append({"status": "skipped", "num": num, "title": chapter_title, "path": str(out_path)})
            continue
        warnings, needs_review = validate_paragraphs(chapter_title, paragraphs)
        chapter = ExtractedChapter(
            title=chapter_title,
            paragraphs=paragraphs,
            source_url="manual-paste",
            source_lang=source_lang,
            warnings=warnings,
            needs_review=needs_review,
        )
        out_path.write_text(render_source_markdown(chapter, "manual-paste", warnings), encoding="utf-8")
        imported += 1
        results.append(
            {
                "status": "imported",
                "num": num,
                "title": chapter_title,
                "path": str(out_path),
                "warnings": warnings,
                "needsReview": needs_review,
            }
        )

    update_novel_json(
        slug,
        title=title or slug,
        author=author,
        source_lang=source_lang,
        source_site="manual-paste",
        source_url="manual-paste",
        total_chapters=len(chunks),
    )
    return {
        "slug": slug,
        "site": "manual-paste",
        "title": title or slug,
        "sourceLang": source_lang,
        "chapterCount": len(chunks),
        "imported": imported,
        "skipped": skipped,
        "failed": 0,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="import_sources")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sites")

    preview = sub.add_parser("preview")
    preview.add_argument("url")
    preview.add_argument("--site", default="auto")

    run = sub.add_parser("run")
    run.add_argument("url")
    run.add_argument("--slug", required=True)
    run.add_argument("--site", default="auto")
    run.add_argument("--range", dest="range_text", default=None)
    run.add_argument("--force", action="store_true")

    recover = sub.add_parser("recover-toc")
    recover.add_argument("--slug", required=True)
    recover.add_argument("--site", default="auto")
    recover.add_argument("--url", default=None)
    recover.add_argument("--dry-run", action="store_true")

    paste = sub.add_parser("paste")
    paste.add_argument("--slug", required=True)
    paste.add_argument("--title", required=True)
    paste.add_argument("--source-lang", default="cn")
    paste.add_argument("--author", default="")
    paste.add_argument("--split-rule", default=None)
    paste.add_argument("--force", action="store_true")
    paste.add_argument("--content", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "sites":
            payload = import_sites()
        elif args.command == "preview":
            payload = preview_url(args.url, args.site)
        elif args.command == "run":
            payload = import_url(args.url, args.slug, args.site, args.range_text, args.force)
        elif args.command == "recover-toc":
            payload = recover_toc(args.slug, args.site, args.url, args.dry_run)
        else:
            content = args.content if args.content is not None else sys.stdin.read()
            payload = import_paste(
                slug=args.slug,
                title=args.title,
                content=content,
                source_lang=args.source_lang,
                author=args.author,
                split_rule=args.split_rule,
                force=args.force,
            )
        print(json.dumps({"ok": True, "data": payload}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
