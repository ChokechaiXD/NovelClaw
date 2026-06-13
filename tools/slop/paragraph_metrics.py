"""paragraph_metrics.py — v2/v3 prose-quality heuristics.

Imported by `slop.scan` and the test suite. Pure functions, no I/O.
"""
import re
import math
import statistics
from collections import Counter


# ── v2: NEW — Em dash statistics ───────────────────────────────────

def em_dash_stats(text: str) -> dict:
    """Count em dashes (—) and classify as body vs. placeholder.

    Body em dash = mid-sentence (surrounded by content on both sides)
    Placeholder = em dash at end of clause or as data marker

    Returns dict with: total, body, placeholder, density (per 1000 chars).
    """
    all_dashes = list(re.finditer(r'—', text))
    total = len(all_dashes)

    body_dashes = 0
    placeholder_dashes = 0
    for m in all_dashes:
        start, end = m.span()
        after = text[end:end + 5].lstrip()
        before = text[max(0, start - 5):start].rstrip()
        # If next char is newline, end of line, or punctuation = placeholder
        if not after or after[0] in '\n\r' or before.endswith((' ', '\t')):
            placeholder_dashes += 1
        else:
            body_dashes += 1

    return {
        'total': total,
        'body': body_dashes,
        'placeholder': placeholder_dashes,
        'density': total / max(1, len(text) / 1000),  # per 1000 chars
    }


# ── v2: NEW — Staccato triplet detection ───────────────────────────

def staccato_check(text: str) -> list[list[str]]:
    """Detect 3+ consecutive short sentences (<20 chars each).

    Staccato triplets read as AI cadence. Should be rare in narrative.

    Returns list of runs (each run is a list of short sentences).
    """
    sentences = re.split(r'[.!?。!?]+\s*', text)
    runs = []
    cur_run = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # Strip 【】 content
        s_clean = re.sub(r'【[^】]*】', '', s).strip()
        if 0 < len(s_clean) <= 20:
            cur_run.append(s_clean)
        else:
            if len(cur_run) >= 3:
                runs.append(cur_run)
            cur_run = []
    if len(cur_run) >= 3:
        runs.append(cur_run)
    return runs


# ── v2: NEW — Sentence type variety ────────────────────────────────

def sentence_variety(text: str) -> dict:
    """Score sentence type diversity: declarative / interrogative /
    exclamatory / fragment / dialogue.

    AI tend to over-produce declarative sentences. Low variety = robotic.

    Returns: {total, types: {label: count}, diversity: 0-1 Shannon entropy}.
    """
    # NOTE: re.split consumes the delimiter — `?`/`!` get stripped from the
    # sentence before we can check `s.endswith('?')`. Use lookbehind to keep
    # the punctuation attached to the preceding sentence.
    sents = [s.strip() for s in re.split(r'(?<=[。.!?！？])\s*', text) if s.strip()]
    if not sents:
        return {'total': 0, 'types': {}, 'diversity': 0.0}

    types = Counter()
    for s in sents:
        if not s:
            continue
        # Dialogue: wrapped in 「」or "" or starts with quote
        if re.match(r'^[「“"].+[」”"]', s) or '"' in s[:3]:
            types['dialogue'] += 1
        elif s.endswith('?') or s.endswith('？'):
            types['interrogative'] += 1
        elif s.endswith('!') or s.endswith('！'):
            types['exclamatory'] += 1
        elif len(s) < 15 and not any(c in s for c in 'กขคงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ'):
            types['fragment'] += 1
        else:
            types['declarative'] += 1

    total = sum(types.values())
    # Shannon entropy
    entropy = 0.0
    for count in types.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    max_entropy = math.log2(max(1, len(types)))
    diversity = entropy / max_entropy if max_entropy > 0 else 0.0
    return {'total': total, 'types': dict(types), 'diversity': diversity}


# ── v2: NEW — Burstiness (sentence length SD) ──────────────────────

def burstiness(text: str) -> dict:
    """SD of sentence lengths. Low SD = monotonous AI rhythm.

    Target: SD > 12 (mix of short/long).

    Returns: {mean, sd, cv (coefficient of variation), samples}.
    """
    sents = [s.strip() for s in re.split(r'[。.!?\n]+', text) if s.strip()]
    sents = [s for s in sents if len(s) > 3]
    if len(sents) < 3:
        return {'mean': 0, 'sd': 0, 'cv': 0, 'samples': len(sents)}
    lens = [len(s) for s in sents]
    mean = statistics.mean(lens)
    sd = statistics.stdev(lens) if len(lens) > 1 else 0
    cv = sd / mean if mean > 0 else 0
    return {'mean': mean, 'sd': sd, 'cv': cv, 'samples': len(sents)}


# ── v2: NEW — Function word diversity (Tier 4.16) ──────────────────

# TH function words that AI overuses — should be <2% of total tokens
FUNC_WORDS = {
    'ก็', 'ครับ', 'ค่ะ', 'ค่า', 'นะ', 'ล่ะ', 'จ้ะ', 'จ้า',
    'เหมือนกัน', 'เช่นกัน', 'เหมือน', 'คล้าย', 'คง', 'อาจ',
    'น่าจะ', 'คงจะ', 'อาจจะ', 'บางที', 'ค่อนข้าง',
    'ที่', 'ซึ่ง', 'อัน', 'สิ่ง', 'อย่าง',
    'เห็นได้ว่า', 'ดั่ง', 'ดั่งที่', 'ดั่งว่า',
    'ขาาา', 'ว่ะ', 'ว่ะ', 'โว้ย',
}


def function_word_diversity(text: str) -> dict:
    """Measure reliance on function words. AI overuses 'ก็', 'ครับ',
    'ขาาา', 'เหมือนกัน' etc. — they should be <2% of total tokens.

    Returns: {function_words: top-15 dict, top_pct: % of total tokens,
              diversity: unique_funcs / total_funcs}.
    """
    # Local import to avoid circular: text_stats imports nothing, this is safe
    from .text_stats import tokenize_th
    tokens = tokenize_th(text)
    if not tokens:
        return {'function_words': {}, 'top_pct': 0, 'diversity': 0}

    func_count = Counter()
    for t in tokens:
        if t in FUNC_WORDS:
            func_count[t] += 1

    total_func = sum(func_count.values())
    top_pct = total_func / max(1, len(tokens)) * 100

    # Diversity = unique function words / total function words
    diversity = len(func_count) / max(1, total_func)

    return {
        'function_words': dict(func_count.most_common(15)),
        'top_pct': top_pct,
        'diversity': diversity,
    }


# ── v2: NEW — Megumin 5-Phase structural check ─────────────────────

def megumin_structural_check(text: str) -> list[str]:
    """Check for structural anti-slop from Megumin V7.

    Flags:
      - 2nd person break (sudden switch from 3rd to 2nd person POV)
      - 3-stage falling (consecutive 3 sentences each shorter)
      - Descriptor echo (same adjective repeated within 200 chars)
      - Ratio inversion (dialogue > narrative block ratio suddenly flipped)
    """
    issues = []

    # 2nd person break: 'คุณ' used as pronoun in 3rd person POV
    # (excluding dialogue and 【】 system messages)
    body_only = re.sub(r'【[^】]*】', '', text)
    body_only = re.sub(r'"[^"]{1,200}"', '', body_only)
    body_only = re.sub(r'「[^」]{1,200}」', '', body_only)
    # Count 'คุณ' that begins a word (preceded by space, punctuation, or
    # start of string). This catches 'คุณเดิน' / 'คุณพูด' (pronoun usage)
    # but NOT compounds like 'ของคุณ' or 'คุณตา' (kinship title).
    # Note: in Thai, words run together — a leading 'คุณ' is almost always
    # a pronoun. This is a heuristic, not perfect.
    you_count = len(re.findall(r'(?:^|[\s\.\?\,\!;:。！？，、：；])คุณ(?!ตา|ยาย|ปู่|ย่า|ลุง|ป้า|น้า|อา|พ่อ|แม่|พี่|น้อง|ชาย|หญิง)', body_only))
    if you_count > 5:
        issues.append(f"2nd person 'คุณ' in 3rd person body: {you_count}x (use pronoun or name)")

    # Descriptor echo: same adjective repeated within 200-char window
    adj_pattern = r'(?:สวย|สง่า|งดงาม|เด่น|ชัด|สดใส|สว่าง|สว่างไสว|เปล่งประกาย|เปล่งรัศมี|แพรวพราว|สงบ|นิ่ง|เย็น|เยือกเย็น)'
    matches = list(re.finditer(adj_pattern, text))
    for i in range(len(matches) - 1):
        if matches[i + 1].start() - matches[i].start() < 200:
            issues.append(f"Descriptor echo: '{matches[i].group()}' → '{matches[i+1].group()}' within 200 chars")
            break  # report first only

    # 3-stage falling: 3 consecutive sentences, each shorter
    sents = [s.strip() for s in re.split(r'[。.!?\n]+', text) if s.strip()]
    for i in range(len(sents) - 2):
        l1, l2, l3 = len(sents[i]), len(sents[i + 1]), len(sents[i + 2])
        if l1 > l2 > l3 and l3 < 15:
            issues.append(f"3-stage falling rhythm at sentence {i}: {l1}>{l2}>{l3}")
            break

    return issues


# ── v3: Per-paragraph metrics ─────────────────────────────────────

def paragraph_metrics(text: str) -> dict:
    """Per-paragraph analysis: dialogue attribution, 【】 density, number forms.

    Returns dict of issue lists + per-paragraph stats.
    """
    from .text_stats import split_paragraphs
    paragraphs = split_paragraphs(text)
    attribution_per_para = []
    brackets_per_para = []
    number_forms = Counter()  # '1,000' vs '1000' vs '1.000'

    for p in paragraphs:
        # Count dialogue attributions per paragraph
        attr = len(re.findall(
            r'(?:เขา|เฉาซิง|หลิวมู่เสวี่ย|เลนนิส|ต้าป่าย|ซาร่า|อาซัม|แอนดรูว์)[^。!?\n「」""]{0,10}'
            r'(?:พูดว่า|กล่าวว่า|บอกว่า|เอ่ยว่า|ถามว่า|ตอบว่า|ตะโกนว่า|เสียงของ)',
            p
        ))
        attribution_per_para.append(attr)

        # Count 【】 system messages per paragraph.
        # Use BOTH 【 and 】 — a single 【event】 can span paragraphs when
        # one para has the opener and the next has the closer.
        brackets = len(re.findall(r'【|】', p))
        brackets_per_para.append(brackets)

        # Number form consistency
        number_forms['with_comma'] += len(re.findall(r'\b\d{1,3},\d{3}\b', p))
        number_forms['with_period'] += len(re.findall(r'\b\d{1,3}\.\d{3}\b', p))
        number_forms['no_sep'] += len(re.findall(r'\b\d{4,}\b', p))

    # 3+ attributions in same paragraph
    heavy_attr_paras = [
        (i, c) for i, c in enumerate(attribution_per_para) if c >= 3
    ]
    # 【】 in 2+ consecutive lines (likely split)
    split_brackets = []
    for i in range(len(brackets_per_para) - 1):
        if brackets_per_para[i] > 0 and brackets_per_para[i + 1] > 0:
            split_brackets.append((i, i + 1))

    return {
        'attribution_per_para': attribution_per_para,
        'brackets_per_para': brackets_per_para,
        'heavy_attr_paras': heavy_attr_paras,
        'split_brackets': split_brackets,
        'number_forms': dict(number_forms),
    }
