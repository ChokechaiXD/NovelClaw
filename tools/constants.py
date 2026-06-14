"""constants.py — Shared constants for NovelClaw tools.

Single source of truth for values used by multiple tools. Import as:

    from constants import LENGTH_RATIO_OK, NAME_CHECKS, NOVEL_ROOT

The CLI dispatcher (novelclaw.py) injects this directory into sys.path,
so tools can also do:

    sys.path.insert(0, str(Path(__file__).parent))
    from constants import LENGTH_RATIO_OK
"""
from pathlib import Path

# Novel-specific paths (root of the global-descent novel)
TOOLS_DIR = Path(__file__).parent
NOVEL_ROOT = TOOLS_DIR.parent / 'novels' / 'global-descent'
GLOSSARY_DIR = NOVEL_ROOT / 'glossary'
CHAPTERS_DIR = NOVEL_ROOT / 'chapters'
SOURCE_DIR = CHAPTERS_DIR / 'source'

# Length ratio bounds for translation vs source (TH natural expansion)
# Below LENGTH_RATIO_OK[0] = too short (likely truncated)
# Above LENGTH_RATIO_OK[1] = too long (likely over-translated / padded)
LENGTH_RATIO_OK = (1.5, 3.0)

# Name consistency checks: (CN, correct Thai, wrong Thai variants to auto-fix)
# If wrong is found AND correct is NOT in text → auto-fix
# If wrong AND correct both found → flag as warning (manual review)
NAME_CHECKS = [
    ('曹星', 'เฉาซิง', 'โจวซิง'),
    ('柳慕雪', 'หลิวมู่เสวี่ย', 'หลิวมู่สวี่'),
    ('陈江', 'เฉินเจียง', 'เฉินเจียงก'),  # 'เฉินเจียงก' = wrong variant with stray ก suffix
    ('香江', 'ฮ่องกง', 'เซียงเจียง'),
    ('极地人', 'คนเมืองหนาว', 'ชาวโพลาร์'),
]
