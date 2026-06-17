"""constants.py — Shared constants for NovelClaw tools.

Single source of truth for values used by multiple tools. Import as:

    from constants import LENGTH_RATIO_OK, NAME_CHECKS, NOVEL_ROOT

Novel selection (priority order):
  1. CLI argument --novel <slug> (handled by each tool's argparse)
  2. Environment variable NOVEL_SLUG
  3. Default: 'global-descent' (backward compatible)

Usage in tools:
    sys.path.insert(0, str(Path(__file__).parent))
    from constants import NOVEL_ROOT, get_novel_root

    # Static (default novel):
    from constants import GLOSSARY_DIR

    # Dynamic (per-novel):
    root = get_novel_root(args.novel)  # from argparse
"""
from pathlib import Path
import os

TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = TOOLS_DIR.parent
NOVELS_DIR = PROJECT_ROOT / 'novels'

# ────────────────────────────────────────────────────────────────────
# Default novel (backward compatible — all existing tools work as-is)
# ────────────────────────────────────────────────────────────────────
_DEFAULT_SLUG = os.environ.get('NOVEL_SLUG', 'global-descent')

NOVEL_ROOT = NOVELS_DIR / _DEFAULT_SLUG
GLOSSARY_DIR = NOVEL_ROOT / 'glossary'
CHAPTERS_DIR = NOVEL_ROOT / 'chapters'
SOURCE_DIR = CHAPTERS_DIR / 'source'


# ────────────────────────────────────────────────────────────────────
# Dynamic novel resolver (for multi-novel support)
# ────────────────────────────────────────────────────────────────────
def get_novel_root(slug: str | None = None) -> Path:
    """Resolve novel root directory.

    Args:
        slug: Novel slug (e.g., 'global-descent', 'another-novel').
              If None, uses default (env var NOVEL_SLUG or 'global-descent').

    Returns:
        Path to the novel's root directory.

    Raises:
        FileNotFoundError: If the novel directory doesn't exist.
    """
    s = slug or _DEFAULT_SLUG
    path = NOVELS_DIR / s
    if not path.exists():
        raise FileNotFoundError(
            f"Novel '{s}' not found at {path}. "
            f"Available: {[d.name for d in NOVELS_DIR.iterdir() if d.is_dir()]}"
        )
    return path


def get_glossary_dir(slug: str | None = None) -> Path:
    return get_novel_root(slug) / 'glossary'


def get_chapters_dir(slug: str | None = None) -> Path:
    return get_novel_root(slug) / 'chapters'


def get_source_dir(slug: str | None = None) -> Path:
    return get_chapters_dir(slug) / 'source'


# ────────────────────────────────────────────────────────────────────
# Translation quality constants
# ────────────────────────────────────────────────────────────────────
import json

_config_path = PROJECT_ROOT / 'validation_config.json'
if _config_path.exists():
    try:
        with open(_config_path, 'r', encoding='utf-8') as _f:
            _shared_config = json.load(_f)
        LENGTH_RATIO_OK = tuple(_shared_config['length_ratio_ok'])
        NAME_CHECKS = [
            (item['cn'], item['correct'], item['wrong'])
            for item in _shared_config['name_checks']
        ]
    except Exception:
        LENGTH_RATIO_OK = (0.6, 3.5)
        NAME_CHECKS = [
            ('曹星', 'เฉาซิง', 'โจวซิง'),
            ('柳慕雪', 'หลิวมู่เสวี่ย', 'หลิวมู่สวี่'),
            ('陈江', 'เฉินเจียง', 'เฉินเจียงก'),
            ('香江', 'ฮ่องกง', 'เซียงเจียง'),
            ('极地人', 'คนเมืองหนาว', 'ชาวโพลาร์'),
        ]
else:
    LENGTH_RATIO_OK = (0.6, 3.5)
    NAME_CHECKS = [
        ('曹星', 'เฉาซิง', 'โจวซิง'),
        ('柳慕雪', 'หลิวมู่เสวี่ย', 'หลิวมู่สวี่'),
        ('陈江', 'เฉินเจียง', 'เฉินเจียงก'),
        ('香江', 'ฮ่องกง', 'เซียงเจียง'),
        ('极地人', 'คนเมืองหนาว', 'ชาวโพลาร์'),
    ]

