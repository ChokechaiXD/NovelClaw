"""novelclaw-quality-report — CLI tool to run quality scoring on translated chapters.

Usage:
  novelclaw-quality-report 100-120                             # score ch 100-120
  novelclaw-quality-report 100-120 --mock                      # mock scores (no LLM)
  novelclaw-quality-report 100-120 --all                       # score ALL existing chapters
  novelclaw-quality-report 100-120 --json                      # output JSON
  novelclaw-quality-report 100-120 --output report.md           # save to file

Pipeline:
  1. Load chapter JSON
  2. Load source .md
  3. Load glossary
  4. Run quality scorer (mock or LLM)
  5. Generate markdown/JSON report
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).parent
_PROJECT_ROOT = _TOOLS_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_TOOLS_DIR))

from constants import CHAPTERS_DIR, SOURCE_DIR, NOVEL_ROOT
from glossary import load_terms
from quality_scorer import build_quality_report, score_translation


def _clean_list_chapters(raw: str, all_flag: bool) -> list[int]:
    """Parse chapter range."""
    if all_flag:
        existing = sorted([
            int(f.stem) for f in CHAPTERS_DIR.glob("*.json")
        ])
        return existing
    if "-" in raw:
        a, b = map(int, raw.split("-"))
        return list(range(a, b + 1))
    return [int(raw)]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        description="Quality scoring for translated chapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s 100-120                     # score ch 100-120
  %(prog)s 100-120 --mock              # mock scores (no LLM)
  %(prog)s --all                       # score ALL existing chapters
  %(prog)s 100-120 --json              # output JSON
  %(prog)s 100-120 --output report.md  # save to file
""",
    )
    ap.add_argument("chapters", nargs="?", default="", help="Single (113) or range (100-120)")
    ap.add_argument("--all", action="store_true", help="Score ALL existing chapters")
    ap.add_argument("--mock", action="store_true", help="Use mock scorer (no LLM)")
    ap.add_argument("--json", action="store_true", help="Output JSON format")
    ap.add_argument("--output", type=str, default="", metavar="FILE", help="Save report to file")
    args = ap.parse_args()

    if not args.all and not args.chapters:
        ap.print_help()
        sys.exit(1)

    chapters = _clean_list_chapters(args.chapters, args.all)
    if not chapters:
        print("No chapters to score.")
        sys.exit(1)

    # Load glossary
    glossary_terms = load_terms()
    print(f"Loaded {len(glossary_terms)} glossary terms")

    # Process chapters
    chapter_data_list: list[dict] = []
    results = []
    passed = 0
    failed = 0

    for ch in chapters:
        json_path = CHAPTERS_DIR / f"{ch:04d}.json"
        src_path = SOURCE_DIR / f"{ch:04d}.md"

        if not json_path.exists():
            print(f"⚠ ch{ch}: no JSON chapter found")
            continue
        if not src_path.exists():
            print(f"⚠ ch{ch}: no source file found")
            continue

        # Load
        chapter_data = json.loads(json_path.read_text(encoding="utf-8"))
        source_text = src_path.read_text(encoding="utf-8")

        # Clean source (strip line numbers, artifacts)
        try:
            from translate import clean_source
            source_text = clean_source(source_text)
        except ImportError:
            pass

        print(f"→ ch{ch}: scoring {len(source_text)} chars...", end=" ")
        sys.stdout.flush()

        score_result = score_translation(
            source_text=source_text,
            chapter_data=chapter_data,
            glossary_terms=glossary_terms,
            mock=args.mock,
            model="haiku",
        )

        chapter_data_list.append(chapter_data)
        results.append(score_result)

        if score_result.parse_error:
            print(f"⚠ parse error: {score_result.parse_error[:80]}")
        elif score_result.passed:
            print(f"✅ {score_result.summary_string()}")
            passed += 1
        else:
            print(f"❌ {score_result.summary_string()}")
            failed += 1

    # Generate report
    report = build_quality_report(chapter_data_list, results)

    if args.json:
        # JSON output
        json_output = {
            "total": len(chapter_data_list),
            "passed": passed,
            "failed": failed,
            "results": [
                r.to_dict() if r else None for r in results
            ],
        }
        print(json.dumps(json_output, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(report)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(report, encoding="utf-8")
        print(f"\nReport saved to: {out_path}")

    print(f"\nTotal: {passed} passed, {failed} failed out of {len(chapter_data_list)}")


if __name__ == "__main__":
    main()
