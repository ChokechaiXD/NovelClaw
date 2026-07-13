"""pipeline — CLI entry point."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import argparse
from .orchestrate import translate_one

ap = argparse.ArgumentParser(description="Test pipeline")
ap.add_argument("ch", type=int, help="Chapter number")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--mock", action="store_true")
ap.add_argument("--from", dest="source_lang", default="auto")
ap.add_argument("--slug", default="global-descent")
args = ap.parse_args()

result = translate_one(
    ch_num=args.ch,
    slug=args.slug,
    source_lang=args.source_lang,
    dry_run=args.dry_run,
    mock=args.mock,
)
