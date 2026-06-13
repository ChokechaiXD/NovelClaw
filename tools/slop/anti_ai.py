"""anti_ai.py — Slop pattern definitions.

Pure data + simple matching functions. No I/O, no path logic.
Imported by `slop.scan` and the test suite.

Pattern sources:
  - TIER1/2/3: NousResearch autonovel/ANTI-SLOP.md
  - ADENAUFAL_T4: adenaufal/anti-slop-writing (Tiers 4.5-4.16)
  - MIKA_PATTERNS: Mika's observed crutches in CN→TH translation
"""
import re
from collections import Counter


# ── Tier 1: kill on sight (EN, kill in any context) ─────────────────
# Sourced from NousResearch autonovel/ANTI-SLOP.md
TIER1 = [
    "delve", "utilize", "leverage", "facilitate", "elucidate", "embark",
    "endeavor", "encompass", "multifaceted", "tapestry", "testament",
    "paradigm", "synergy", "synergize", "holistic", "catalyze", "catalyst",
    "juxtapose", "nuanced", "realm", "myriad", "plethora",
    # Adenaufal adds:
    "vibrant", "vital", "pivotal", "profound", "intricate", "embark",
    "harness", "foster", "cultivate", "bolster", "galvanize",
]

# Auto-expand TIER1 with common inflections to catch "leverages" / "leveraged".
# For words ending in 'e' (utilize, delve), the past tense is 'utilized' not
# 'utilizeed' — strip the trailing 'e' before adding 'ed'/'ing'.
def _past(w: str) -> str:
    return w[:-1] + 'ed' if w.endswith('e') else w + 'ed'


def _ing(w: str) -> str:
    return w[:-1] + 'ing' if w.endswith('e') else w + 'ing'


TIER1_VARIANTS = tuple(
    TIER1
    + [w + "s" for w in TIER1]
    + [_past(w) for w in TIER1]
    + [_ing(w) for w in TIER1]
    + [w + "ly" for w in TIER1]
)


# ── Tier 2: clusters of 3+ per paragraph (EN) ───────────────────────
TIER2 = [
    "robust", "comprehensive", "seamless", "seamlessly", "cutting-edge",
    "innovative", "streamline", "empower", "elevate",
    "optimize", "scalable", "resonate", "underscore",
    "cornerstone", "game-changer", "ever-evolving", "groundbreaking",
]


# ── Tier 3: filler phrases (EN + TH + Mika crutches) ────────────────
TIER3_PHRASES = [
    # EN
    "It's worth noting that", "It is worth noting that",
    "It's important to note that", "Importantly,",
    "Notably,", "Interestingly,", "Let's dive into", "Let's explore",
    "In this section,", "As we can see,", "As mentioned earlier,",
    "In conclusion,", "To summarize,", "Furthermore,",
    "Moreover,", "Additionally,", "At the end of the day,",
    "It goes without saying", "Without further ado",
    "When it comes to", "In the realm of", "One might argue",
    "This begs the question", "Not just", "A comprehensive approach",
    "A holistic approach", "A nuanced approach",
    # TH translation crutches (CN→TH specific)
    "อย่างที่คาดไว้", "น่าสังเกต", "น่าสนใจ",
    "นอกจากนี้", "ดังนั้น", "อย่างไรก็ตาม", "ทั้งนี้", "อย่างไรก็ดี",
    "รวมถึง", "โดยเฉพาะ", "นับตั้งแต่", "ในขณะเดียวกัน",
    "ถึงแม้ว่า", "แม้ว่า", "ถ้าหากว่า", "หากว่า", "เพื่อที่จะ",
    "เนื่องจากว่า", "อันที่จริง", "อันที่จริงแล้ว",
    # Mika-specific crutches
    "ดีใจในใจ", "เสียใจในใจ", "โกรธในใจ", "กลัวในใจ",
    "เต็มไปด้วยความ", "ชาวอาณานิคม",  # followed by name = appositive
    "รู้สึกว่า", "รู้สึกถึง", "รู้สึกได้ถึง",  # weak perception verbs
    "เป็นอันที่น่า", "ทำให้รู้สึก",  # generic "makes one feel"
]


# ── Tier 4: Adenaufal structural anti-slop (16 sub-tiers) ──────────
# Regex-based + heuristic checks. Source: adenaufal/anti-slop-writing
ADENAUFAL_T4 = [
    # 4.5: Participial -ing overuse (decorative continuous)
    (r'\b\w+ing\b', "T4.5: participle -ing", "EN only — TH skip"),
    # 4.6: Rule of three (3 items in series, especially in 3+ sentences)
    # 4.7: Copula avoidance — "isn't just X, it's Y" / "serves as"
    (r"(?:isn't|is\s+not)\s+just\s+[^.!?]{1,40}?,\s*it'?s", "T4.7: copula avoidance 'isn't just X, it's Y'"),
    (r"serves\s+as\s+(?:a|an|the)\s+", "T4.7: 'serves as a/an/the' filler"),
    # 4.8: False ranges (X to Y where Y is extreme)
    (r"from\s+\w+\s+to\s+(?:extreme|ultimate|absolute|unprecedented)",
     "T4.8: false range 'from X to extreme'"),
    # 4.9: "Despite challenges" / "Despite adversity" framing
    (r"despite\s+(?:the\s+)?(?:challenges|adversity|obstacles|difficulties)",
     "T4.9: 'Despite challenges' framing"),
    # 4.10: Em dash overuse (Adenaufal: "THE #1 AI tell")
    # — counted separately in em_dash_stats, but flag clustered uses
    # 4.11: Negative parallelisms ("Not just X, but Y")
    (r"not\s+just\s+[^.!?]{1,40}?,\s+but\s+", "T4.11: negative parallelism 'not just X, but Y'"),
    # 4.12: Em dash in body (counted separately)
    # 4.13: Staccato triplets (3+ short consecutive sentences)
    # — counted separately in staccato_check
    # 4.14: Sentence type variety
    # — counted separately in sentence_variety
    # 4.15: Model tells (Mika custom: subject echo, emotion lumps)
    # — MIKA_PATTERNS
    # 4.16: Function word diversity
    # — counted separately in function_word_diversity
]


# ── Mika-specific regex patterns ────────────────────────────────────
MIKA_PATTERNS = [
    # Subject echo: 3+ consecutive sentences starting with same name
    (r'(?:เฉาซิง[^\n]{0,80}\n){3,}',
     "Subject echo: 3+ sentences starting with เฉาซิง"),
    (r'(?:หลิวมู่เสวี่ย[^\n]{0,80}\n){3,}',
     "Subject echo: 3+ sentences starting with หลิวมู่เสวี่ย"),
    (r'(?:ต้าป่าย[^\n]{0,80}\n){3,}',
     "Subject echo: 3+ sentences starting with ต้าป่าย"),
    # Flat emotion lumps
    (r'(?:สีหน้า|ดวงตา|น้ำเสียง)[^\n]{0,20}(?:เปี่ยม|เต็มไป)[^\n]{0,30}(?:ความ[^\n]{0,30})',
     "Flat emotion lump: 'สีหน้าเปี่ยมด้วยความ...' pattern"),
    # Appositive compound
    (r'(?:ชาว(?:อาณานิคม|อาณาเขต))[ก-๙]{2,15}(?=\s|$)',
     "Appositive: 'ชาวอาณานิคม[ชื่อ]' (flip to '[ชื่อ] ชาว...')"),
    # Direction/sequence error
    (r'ข้างหน้า(?!.{0,5}(?:จะ|ของ))', "Direction error: 'ข้างหน้า' (use 'แรก' for 'preceding')"),
    # Generic perception verbs (Tier 4.15 Mika custom)
    (r'รู้สึก(?:ว่า|ถึง|ได้ถึง)', "Weak perception: 'รู้สึก' (try concrete sensation)"),
    # "It seems that" filler
    (r'(?:ดูเหมือนว่า|ราวกับว่า)\s+', "Filler: 'ดูเหมือนว่า' / 'ราวกับว่า' (use sparingly)"),
    # Game stat acronym
    (r'\b(?:HP|MP|XP|ATK|DEF)\b', "Game stat acronym (consider translating or stylizing)"),
    # 3+ em dashes in one paragraph (heavy placeholder = Ground Truth fail)
    (r'—[^.\n]{0,200}—[^.\n]{0,200}—', "Multiple em dashes in paragraph (likely missing data)"),
    # v3: Dialogue attribution overuse
    (r'(?:เขา|เฉาซิง|หลิวมู่เสวี่ย|เลนนิส|ต้าป่าย|ซาร่า|อาซัม|แอนดรูว์)[^。!?\n「」""]{0,10}(?:พูดว่า|กล่าวว่า|บอกว่า|เอ่ยว่า|ถามว่า|ตอบว่า|ตะโกนว่า|เสียงของ)',
     "Dialogue attribution: 'X พูด/กล่าว/บอก/เอ่ย/ถาม' (use bare dialogue or simple tag)"),
    # v3: Verbose speech tags
    (r'เสียง(?:ของ|แว่ว|ดัง|ดังขึ้น|เบา|เบาลง|ดังลั่น|หนักแน่น|นุ่ม|แหบ)',
     "Verbose speech tag: 'เสียงของ/แว่ว/ดังขึ้น' (cut or rephrase)"),
    # v3: Multi-line 【】 split (one event in 2+ blocks)
    # Hard to detect without context — flagged in v4 with state
]


# ── Matcher functions (pure, testable) ──────────────────────────────

def find_tier1(text: str) -> dict[str, int]:
    """Find Tier 1 slop words (kill on sight). Returns {word: count}."""
    hits = Counter()
    for word in TIER1_VARIANTS:
        count = len(re.findall(rf'\b{re.escape(word)}\b', text, re.IGNORECASE))
        if count:
            hits[word] += count
    return dict(hits)


def find_tier2(text: str) -> dict[str, int]:
    """Find Tier 2 slop words. Returns {word: count}."""
    hits = Counter()
    for word in TIER2:
        count = len(re.findall(rf'\b{re.escape(word)}\b', text, re.IGNORECASE))
        if count:
            hits[word] += count
    return dict(hits)


def find_tier3(text: str) -> dict[str, int]:
    """Find Tier 3 phrases (multi-word). Returns {phrase: count}."""
    hits = Counter()
    for phrase in TIER3_PHRASES:
        count = text.count(phrase)
        if count:
            hits[phrase] += count
    return dict(hits)


def find_mika_patterns(text: str) -> list[tuple[str, str]]:
    """Find Mika-specific patterns. Returns [(description, matched_text), ...]."""
    results = []
    for pat, desc in MIKA_PATTERNS:
        for m in re.finditer(pat, text):
            results.append((desc, m.group()[:80]))
    return results


def find_adenaufal(text: str) -> list[tuple[str, str]]:
    """Find Adenaufal T4 structural patterns. Returns [(description, matched), ...]."""
    results = []
    for pat, desc, *skip in ADENAUFAL_T4:
        # skip flag is for patterns that don't apply to TH translations
        if skip and skip[0] == "EN only — TH skip":
            continue
        for m in re.finditer(pat, text, re.IGNORECASE):
            results.append((desc, m.group()[:80]))
    return results
