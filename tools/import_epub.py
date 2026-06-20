#!/usr/bin/env python

"""
NovelClaw EPUB Import Utility (Tier 2)
Parses EPUB using Python's standard library (zipfile, ElementTree)
Extracts chapters, normalizes to clean markdown paragraphs, and saves to chapters/source/.
"""

import argparse
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import unquote


def strip_ns(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_html_to_markdown(html_bytes):
    html_content = html_bytes.decode("utf-8", errors="ignore")

    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    title = re.sub(r"<[^>]+>", "", title)  # clean HTML tags from title

    # Strip script, style elements
    html_content = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", html_content, flags=re.IGNORECASE)
    html_content = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html_content, flags=re.IGNORECASE)

    # Unescape some common HTML entities
    html_content = html_content.replace("&nbsp;", " ").replace("&#160;", " ")

    # Fast regex parsing for paragraph blocks. ElementTree is too strict for poorly-formed XHTML
    paragraphs = []

    # Find headings and paragraphs in order of appearance
    # Match tags: <h1> to <h6>, <p>, or <div class="paragraph"> etc.
    element_pattern = re.compile(r"<(h[1-6]|p)(?:\s[^>]*)?>(.*?)</\1>", re.IGNORECASE | re.DOTALL)

    for tag_name, inner_html in element_pattern.findall(html_content):
        # Strip all HTML tags from the inner content
        clean_text = re.sub(r"<[^>]+>", "", inner_html).strip()
        # Clean entities
        clean_text = (
            clean_text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )
        # Collapse multiple spaces
        clean_text = re.sub(r"\s+", " ", clean_text)

        if clean_text:
            if tag_name.lower().startswith("h"):
                level = int(tag_name[1])
                paragraphs.append(f"{'#' * level} {clean_text}")
            else:
                paragraphs.append(clean_text)

    # Fallback if no tags matched: split by lines/br tags
    if not paragraphs:
        text_only = re.sub(r"<br\s*/?>", "\n", html_content, flags=re.IGNORECASE)
        text_only = re.sub(r"<[^>]+>", "", text_only)
        text_only = (
            text_only.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
        )
        lines = [line.strip() for line in text_only.split("\n") if line.strip()]
        paragraphs = lines

    return title, paragraphs


def import_epub(epub_path, novel_root, start_num=1):
    if not zipfile.is_zipfile(epub_path):
        return {"ok": False, "error": "The uploaded file is not a valid zip/epub file."}

    try:
        with zipfile.ZipFile(epub_path, "r") as z:
            # 1. Parse container.xml to locate OPF file
            try:
                container_data = z.read("META-INF/container.xml").decode("utf-8", errors="ignore")
                container_data = re.sub(r'\s+xmlns="[^"]+"', "", container_data)
                root = ET.fromstring(container_data)
                rootfile = root.find(".//rootfile")
                if rootfile is None:
                    return {
                        "ok": False,
                        "error": "Invalid EPUB: META-INF/container.xml is missing <rootfile>",
                    }
                opf_path = Path(rootfile.attrib.get("full-path", ""))
            except Exception as e:
                return {"ok": False, "error": f"Failed to locate content.opf: {str(e)}"}

            # 2. Parse OPF file
            opf_dir = opf_path.parent
            opf_data = z.read(opf_path.as_posix()).decode("utf-8", errors="ignore")
            opf_data = re.sub(r'\s+xmlns="[^"]+"', "", opf_data)

            try:
                opf_root = ET.fromstring(opf_data)
            except Exception as e:
                return {"ok": False, "error": f"Failed to parse content.opf XML: {str(e)}"}

            # Find manifest items
            manifest_items = {}
            manifest_section = opf_root.find("manifest")
            if manifest_section is not None:
                for item in manifest_section.findall("item"):
                    item_id = item.attrib.get("id")
                    href = item.attrib.get("href")
                    if item_id and href:
                        manifest_items[item_id] = href

            # Find spine items (reading order)
            spine_order = []
            spine_section = opf_root.find("spine")
            if spine_section is not None:
                for itemref in spine_section.findall("itemref"):
                    idref = itemref.attrib.get("idref")
                    if idref and idref in manifest_items:
                        spine_order.append(manifest_items[idref])

            if not spine_order:
                return {
                    "ok": False,
                    "error": "EPUB spine is empty (no chapters found in reading order).",
                }

            # Create output directories
            source_dir = Path(novel_root) / "chapters" / "source"
            source_dir.mkdir(parents=True, exist_ok=True)

            imported_count = 0
            chapters_metadata = []

            # 3. Read and extract each chapter
            curr_num = start_num
            for href in spine_order:
                # Handle relative paths in zip file
                # Unquote URL-encoded filenames
                raw_href = unquote(href)
                target_path = (opf_dir / raw_href).as_posix()

                # Check if file exists in ZIP (it might be e.g. OEBPS/text/ch01.xhtml)
                if target_path not in z.namelist():
                    # Retry with exact manifest filename relative to root
                    if raw_href in z.namelist():
                        target_path = raw_href
                    else:
                        # Find closest matching filename in zip list
                        matches = [
                            name for name in z.namelist() if name.endswith(Path(raw_href).name)
                        ]
                        if matches:
                            target_path = matches[0]
                        else:
                            continue  # skip if not found

                # Read xhtml file
                try:
                    html_bytes = z.read(target_path)
                except Exception:
                    continue  # skip files that fail to read

                title, paragraphs = parse_html_to_markdown(html_bytes)

                # Skip files that have no content (e.g. cover page, stylesheet placeholders)
                total_text_length = sum(len(p) for p in paragraphs)
                if total_text_length < 100 and not title:
                    continue

                # Format to Markdown
                padded_num = f"{curr_num:04d}"
                md_title = title if title else f"ตอนที่ {curr_num}"

                md_content = f"# {md_title}\n\n"
                md_content += "\n\n".join(paragraphs)
                md_content += "\n\n(จบบท)\n"

                # Write to source directory
                out_path = source_dir / f"{padded_num}.md"
                with out_path.open("w", encoding="utf-8") as f:
                    f.write(md_content)

                chapters_metadata.append(
                    {"num": curr_num, "title": md_title, "filename": f"{padded_num}.md"}
                )

                imported_count += 1
                curr_num += 1

            return {"ok": True, "importedCount": imported_count, "chapters": chapters_metadata}

    except Exception as e:
        return {"ok": False, "error": f"Internal error during EPUB extraction: {str(e)}"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import EPUB chapters into NovelClaw raw source format."
    )
    parser.add_argument("--epub", required=True, help="Path to the source EPUB file.")
    parser.add_argument(
        "--novel-root", required=True, help="Path to the target novel root directory."
    )
    parser.add_argument(
        "--start-num", type=int, default=1, help="Starting chapter number (default 1)."
    )

    args = parser.parse_args()

    res = import_epub(args.epub, args.novel_root, args.start_num)
    print(json.dumps(res, indent=2, ensure_ascii=False))
