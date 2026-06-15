"""pre_chapter.py — Prep context for the NEXT chapter Mika will translate.

Thin wrapper around translate_next.py for backward compatibility.
All logic lives in translate_next.py.

Usage:
  python pre_chapter.py            # next chapter (from progress.md)
  python pre_chapter.py 81         # specific chapter number
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from translate_next import main  # noqa: E402

if __name__ == "__main__":
    main()
