#!/usr/bin/env python3
"""validate_data.py — JSON schema validation for NovelClaw data files.

Usage:
    python tools/validate_data.py --novel <slug>          # Validate all chapter JSONs
    python tools/validate_data.py --file <path>           # Validate single file
    python tools/validate_data.py --all                   # Validate all novels

Exit code: 0 = all valid, 1 = any file invalid
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "tools" / "schema"


def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    if not path.exists():
        print(f"  ⏭️  Schema not found: {name}")
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_json(data: dict, schema: dict) -> list[str]:
    """Simple structural validation without jsonschema dependency.
    Checks required fields, types, and enums.
    """
    errors = []

    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Check property types and constraints
    props = schema.get("properties", {})
    for field, field_schema in props.items():
        if field not in data:
            continue
        val = data[field]

        # Type check
        expected_type = field_schema.get("type")
        if expected_type == "string" and not isinstance(val, str):
            errors.append(f"Field '{field}' should be string, got {type(val).__name__}")
        elif expected_type == "integer" and not isinstance(val, int):
            errors.append(f"Field '{field}' should be integer, got {type(val).__name__}")
        elif expected_type == "array" and not isinstance(val, list):
            errors.append(f"Field '{field}' should be array, got {type(val).__name__}")
        elif expected_type == "object" and not isinstance(val, dict):
            errors.append(f"Field '{field}' should be object, got {type(val).__name__}")

        # Minimum check for integers
        minimum = field_schema.get("minimum")
        if isinstance(val, int) and minimum is not None and val < minimum:
            errors.append(f"Field '{field}' = {val} < minimum ({minimum})")

        # Enum check
        enum_vals = field_schema.get("enum")
        if enum_vals and val not in enum_vals:
            errors.append(f"Field '{field}' = '{val}' not in allowed values: {enum_vals}")

        # Pattern check
        pattern = field_schema.get("pattern")
        if pattern and isinstance(val, str):
            import re
            if not re.match(pattern, val):
                errors.append(f"Field '{field}' = '{val}' does not match pattern: {pattern}")

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
        print(f"  ⏭️  {path.name}: No schema to validate against")
        return True

    errors = validate_json(data, schema)

    # Extra: check chapterNo matches filename
    expected_num = int(path.stem.split(".")[0])
    if data.get("chapterNo") != expected_num:
        errors.append(f"chapterNo ({data.get('chapterNo')}) does not match filename ({expected_num})")

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
                errors = validate_json(data, schema)
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
        print(f"  ✓ chapters.json (exists)")
    else:
        print(f"  ⚠️  chapters.json missing")

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
        # Validate all novels
        novels_dir = ROOT / "novels"
        for d in sorted(novels_dir.iterdir()):
            if d.is_dir():
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
