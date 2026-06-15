"""Build glossary.yml + style_rules.yml from .md source files.

The .md files are human-readable. The .yml files are machine-readable.
Both should be in sync — this script is the canonical bridge.

Usage:
    python tools/build_yaml.py                  # Build both .yml files
    python tools/build_yaml.py --check          # Exit 1 if .yml out of date
"""
import re
import sys
from pathlib import Path

_GLOSSARY_DIR_DEFAULT = Path(__file__).parent.parent / "novels" / "global-descent" / "glossary"
_NOVEL_DIR_DEFAULT = Path(__file__).parent.parent / "novels" / "global-descent"

# === Table parser ===

ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|$")


def parse_table_rows(text: str, priority_hint: int | None = None) -> list[dict]:
    """Parse all `| a | b | c | d | e |` rows from a markdown file.
    Skips headers, separators, blank lines, and **bold** section markers.
    """
    rows = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        source, thai, category, priority, notes = m.groups()
        # Skip header row
        if source.strip() == "Source" or source.strip().startswith("---"):
            continue
        if not source.strip() or not thai.strip():
            continue
        try:
            prio = int(priority.strip())
        except (ValueError, TypeError):
            prio = priority_hint or 3
        rows.append({
            "source": source.strip(),
            "thai": thai.strip(),
            "category": category.strip(),
            "priority": prio,
            "notes": notes.strip(),
        })
    return rows


def parse_locked(path: Path) -> list[dict]:
    """Parse locked.md — locks have priority 3 unless marked 1 in tables.
    The file is structured: Priority 1 section then Priority 2/3 sections.
    """
    rows = parse_table_rows(path.read_text(encoding="utf-8"), priority_hint=3)
    return rows


def parse_priority_table(path: Path) -> list[dict]:
    """Parse reference.md or auto.md — single priority table."""
    return parse_table_rows(path.read_text(encoding="utf-8"), priority_hint=3)


# === YAML builder (minimal, no pyyaml dep) ===

def _yaml_quote(s: str) -> str:
    """Quote a YAML string if it contains special chars or starts with one.
    Always-quote is safest for our content (markdown-derived text).
    """
    if not s:
        return '""'
    # Always single-quote our content — backslash-escape internal ' as ''
    # Single-quoted YAML: '' represents a single ', no other escapes needed
    return "'" + s.replace("'", "''") + "'"


def to_yaml(rows: list[dict], keys_order: list[str]) -> str:
    """Render a list of dicts as YAML block-style. Stable ordering.
    Always-quotes string values to avoid YAML parser surprises (* & ! etc).
    """
    lines: list[str] = []
    for row in rows:
        first = True
        for k in keys_order:
            v = row.get(k, "")
            v_str = "" if v is None else str(v)
            prefix = "- " if first else "  "
            lines.append(f"{prefix}{k}: {_yaml_quote(v_str)}")
            first = False
        lines.append("")
    return "\n".join(lines)


# === Style rules extraction ===

def parse_style_rules(path: Path) -> dict:
    """Parse style.md into structured rules.

    Returns:
        {
            "term_choices": [...],  # from "Specific term choices (locked)"
            "punctuation": [...],
            "naturalness": [...],   # from "Top 5 things..."
            "banned_patterns": [...],  # from "Banned patterns" section
            "slop_candidates": [...],
            "policies": [...],
        }
    """
    text = path.read_text(encoding="utf-8")

    rules: dict[str, list[dict]] = {
        "term_choices": [],
        "punctuation": [],
        "naturalness": [],
        "banned_patterns": [],
        "slop_candidates": [],
        "policies": [],
    }

    current_section = None

    for line in text.splitlines():
        # Detect section headers
        if line.startswith("## "):
            header = line[3:].strip()
            if "term choices" in header.lower():
                current_section = "term_choices"
            elif "punctuation" in header.lower() or "formatting" in header.lower():
                current_section = "punctuation"
            elif "naturalness" in header.lower() or "thai" in header.lower() and "natural" in header.lower():
                current_section = "naturalness"
            elif "banned" in header.lower():
                current_section = "banned_patterns"
            elif "slop" in header.lower():
                current_section = "slop_candidates"
            elif "policy" in header.lower() or "adult" in header.lower() or "explicit" in header.lower():
                current_section = "policies"
            else:
                current_section = None
            continue

        if not current_section or not line.strip():
            continue

        # Parse bullet points
        bullet_match = re.match(r"^[\s]*[-*]\s+(.+)$", line)
        if bullet_match:
            content = bullet_match.group(1).strip()
            # Try to extract bold key + value
            bold_match = re.match(r"^\*\*(.+?)\*\*\s*[:：—–-]\s*(.+)$", content)
            if bold_match:
                rules[current_section].append({
                    "key": bold_match.group(1).strip(),
                    "value": bold_match.group(2).strip(),
                })
            else:
                rules[current_section].append({"text": content})
            continue

        # Numbered list (Top 5 naturalness)
        num_match = re.match(r"^[\s]*\d+\.\s+\*\*(.+?)\*\*\s*[:：—–-]?\s*(.+)$", line)
        if num_match and current_section == "naturalness":
            rules[current_section].append({
                "key": num_match.group(1).strip(),
                "value": num_match.group(2).strip(),
            })

    return rules


# === Main ===

def main() -> int:
    locked_path = _GLOSSARY_DIR_DEFAULT / "locked.md"
    reference_path = _GLOSSARY_DIR_DEFAULT / "reference.md"
    auto_path = _GLOSSARY_DIR_DEFAULT / "auto.md"
    style_path = _NOVEL_DIR_DEFAULT / "style.md"

    # Parse all
    locked = parse_locked(locked_path)
    reference = parse_priority_table(reference_path)
    auto = parse_priority_table(auto_path)
    style = parse_style_rules(style_path)

    # Dedupe by source (locked wins)
    seen = set()
    all_terms: list[dict] = []
    for term in locked:
        if term["source"] not in seen:
            seen.add(term["source"])
            term["lock"] = "locked"
            all_terms.append(term)
    for term in reference:
        if term["source"] not in seen:
            seen.add(term["source"])
            term["lock"] = "reference"
            all_terms.append(term)
    for term in auto:
        if term["source"] not in seen:
            seen.add(term["source"])
            term["lock"] = "auto"
            all_terms.append(term)

    # Build glossary.yml
    glossary_yml = (
        "# Auto-generated by tools/build_yaml.py — DO NOT EDIT BY HAND\n"
        "# Source: novels/global-descent/glossary/{locked,reference,auto}.md\n"
        "# Edit .md, then run `python tools/build_yaml.py` to regenerate.\n"
        f"# Terms: {len(all_terms)} ({len(locked)} locked, {len(reference)} reference, {len(auto)} auto)\n"
        "\n"
        "terms:\n"
        + to_yaml(all_terms, ["source", "thai", "category", "priority", "lock", "explanation", "notes"])
    )

    # Build style_rules.yml
    style_yml_lines = [
        "# Auto-generated by tools/build_yaml.py — DO NOT EDIT BY HAND",
        "# Source: novels/global-descent/style.md",
        "",
    ]
    for section, items in style.items():
        if not items:
            continue
        style_yml_lines.append(f"{section}:")
        for item in items:
            if "key" in item:
                style_yml_lines.append(f"  - key: {_yaml_quote(item['key'])}")
                style_yml_lines.append(f"    value: {_yaml_quote(item['value'])}")
            else:
                style_yml_lines.append(f"  - text: {_yaml_quote(item['text'])}")
        style_yml_lines.append("")

    style_yml = "\n".join(style_yml_lines)

    # Write
    glossary_out = _GLOSSARY_DIR_DEFAULT / "glossary.yml"
    style_out = _NOVEL_DIR_DEFAULT / "style_rules.yml"

    if "--check" in sys.argv:
        # Verify files match
        cur_g = glossary_out.read_text(encoding="utf-8") if glossary_out.exists() else ""
        cur_s = style_out.read_text(encoding="utf-8") if style_out.exists() else ""
        if cur_g != glossary_yml:
            print(f"OUT OF DATE: {glossary_out}")
            return 1
        if cur_s != style_yml:
            print(f"OUT OF DATE: {style_out}")
            return 1
        print("YAML files up to date.")
        return 0

    glossary_out.write_text(glossary_yml, encoding="utf-8")
    style_out.write_text(style_yml, encoding="utf-8")

    print(f"Wrote {glossary_out} ({len(all_terms)} terms)")
    print(f"  Locked: {len(locked)}, Reference: {len(reference)}, Auto: {len(auto)}")
    print(f"Wrote {style_out}")
    for section, items in style.items():
        if items:
            print(f"  {section}: {len(items)} rules")

    return 0


if __name__ == "__main__":
    sys.exit(main())
