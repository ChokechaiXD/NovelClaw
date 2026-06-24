#!/usr/bin/env python3
"""validate_data.py — JSON schema validation for NovelClaw data files.

Uses jsonschema Draft7Validator with FormatChecker for deep validation.
Validates nested objects, arrays, enums, formats, and filename-matching.

Usage:
    python tools/validate_data.py --novel <slug>
    python tools/validate_data.py --file <path>
    python tools/validate_data.py --all

Exit code: 0 = all valid, 1 = any file invalid
"""

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "tools" / "schema"


def load_schema(name: str) -> dict | None:
    path = SCHEMA_DIR / name
    if not path.exists():
        print(f"  ⏭️  Schema not found: {name}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_with_schema(data: dict, schema: dict) -> list[str]:
    """Validate data against jsonschema Draft7 with format checking."""
    errors = []
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    for err in sorted(validator.iter_errors(data), key=lambda e: e.path):
        path = " → ".join(str(p) for p in err.path) if err.path else "root"
        msg = err.message
        # Add context for enum errors
        if err.validator == "enum":
            msg += f" (allowed: {err.validator_value})"
        errors.append(f"[{path}] {msg}")
    return errors


def validate_chapter_file(path: Path) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ❌ {path.name}: Invalid JSON — {e}")
        return False

    schema = load_schema("chapter.schema.json")
    if not schema:
        print(f"  ⏭️  {path.name}: No schema")
        return True

    errors = validate_with_schema(data, schema)

    # Extra: check chapterNo matches filename
    stem = path.stem  # e.g. "0001.th" or "0042"
    file_num_match = re.match(r"(\d+)", stem)
    if file_num_match:
        expected_num = int(file_num_match.group(1))
        actual = data.get("chapterNo")
        if actual is not None and actual != expected_num:
            errors.append(f"[filename] chapterNo ({actual}) does not match filename ({expected_num})")

    if errors:
        print(f"  ❌ {path.name}:")
        for e in errors:
            print(f"      • {e}")
        return False
    print(f"  ✓ {path.name}")
    return True


def validate_novel_dir(slug: str, novel_dir: Path) -> bool:
    print(f"\n📖 Validating: {slug}")
    all_ok = True

    # Validate novel.json
    novel_json = novel_dir / "novel.json"
    if novel_json.exists():
        try:
            with open(novel_json) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"  ❌ novel.json: Invalid JSON")
            all_ok = False
        else:
            schema = load_schema("novel.schema.json")
            if schema:
                errors = validate_with_schema(data, schema)
                if errors:
                    print(f"  ❌ novel.json:")
                    for e in errors:
                        print(f"      • {e}")
                    all_ok = False
                else:
                    print(f"  ✓ novel.json")
    else:
        print(f"  ⏭️  novel.json not found")

    # Validate chapters.json
    ch_json = novel_dir / "chapters.json"
    if ch_json.exists():
        # Light check: is it valid list or dict structure?
        try:
            ch_data = json.loads(ch_json.read_text(encoding="utf-8"))
            if isinstance(ch_data, dict):
                ch_list = ch_data.get("chapters", [])
            elif isinstance(ch_data, list):
                ch_list = ch_data
            else:
                ch_list = []
            print(f"  ✓ chapters.json ({len(ch_list)} entries)")
        except (json.JSONDecodeError, OSError):
            print(f"  ❌ chapters.json: Invalid JSON")
            all_ok = False
    else:
        print(f"  ⚠️  chapters.json missing")

    # Validate search-index.json
    si_path = novel_dir / "search-index.th.json"
    if si_path.exists():
        try:
            si_data = json.loads(si_path.read_text(encoding="utf-8"))
            entries = si_data.get("entries", [])
            # Check entry structure
            si_ok = True
            for i, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    print(f"  ❌ search-index.th.json entry [{i}]: not an object")
                    si_ok = False
                    continue
                if "num" not in entry:
                    print(f"  ❌ search-index.th.json entry [{i}]: missing 'num'")
                    si_ok = False
                if "text" in entry and len(entry["text"]) > 15000:
                    print(f"  ⚠️  search-index.th.json entry [{i}]: text > 15K chars ({len(entry['text'])}")
            if si_ok:
                print(f"  ✓ search-index.th.json ({len(entries)} entries)")
        except (json.JSONDecodeError, OSError):
            print(f"  ❌ search-index.th.json: Invalid JSON")
            all_ok = False
    else:
        print(f"  ⏭️  search-index.th.json not found")

    # Validate all chapter files
    ch_dir = novel_dir / "chapters"
    if ch_dir.exists():
        for f in sorted(ch_dir.glob("*.json")):
            if f.name == "index.json":
                continue
            if not validate_chapter_file(f):
                all_ok = False

    return all_ok


def main():
    args = sys.argv[1:]
    errors = 0

    if not args or "--all" in args:
        novels_dir = ROOT / "novels"
        for d in sorted(novels_dir.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                if not validate_novel_dir(d.name, d):
                    errors += 1

    elif args[0] == "--novel" and len(args) >= 2:
        slug = args[1]
        novel_dir = ROOT / "novels" / slug
        if not novel_dir.exists():
            print(f"❌ Novel '{slug}' not found")
            sys.exit(1)
        if not validate_novel_dir(slug, novel_dir):
            errors += 1

    elif args[0] == "--file" and len(args) >= 2:
        path = Path(args[1])
        if not path.exists():
            print(f"❌ File not found: {path}")
            sys.exit(1)
        if not validate_chapter_file(path):
            errors += 1

    else:
        print("Usage:")
        print("  python tools/validate_data.py --all")
        print("  python tools/validate_data.py --novel <slug>")
        print("  python tools/validate_data.py --file <path>")
        sys.exit(1)

    print(f"\n{'=' * 40}")
    if errors:
        print(f"❌ {errors} file(s) failed validation")
        sys.exit(1)
    else:
        print("✅ All files valid")
        sys.exit(0)


if __name__ == "__main__":
    main()
