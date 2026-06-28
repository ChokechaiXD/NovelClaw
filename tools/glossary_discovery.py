#!/usr/bin/env python3
"""
glossary_discovery.py — Auto term discovery for NovelClaw.

หลังแปลเสร็จ → scan source → เจอคำที่ไม่อยู่ใน glossary
→ ใช้ LLM เสนอคำแปล → เพิ่มเข้า glossary.json อัตโนมัติ

Architecture:
  - Uses a SEPARATE model (judge/discovery model) from translate model
  - Runs after Station 6.75 (Judge), before final save
  - Only processes terms that appear 2+ times in source (confidence filter)
  - Saves to glossary.json with priority=3 (auto) + notes="auto_discovered"
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# ── Paths ──────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── CJK term extraction ───────────────────────────────────────────────

# Terms that are clearly UI noise — skip these always
_UI_NOISE = {
    "首頁", "科幻小說", "玄幻小說", "都市言情", "歷史軍事", "遊戲競技",
    "加入書籤", "小說報錯", "投票推薦", "字體", "上一章", "下一章", "目錄",
    "關燈", "開燈", "下載", "客戶端", "手機看書", "繁體", "簡體",
    "上一頁", "下一頁", "返回", "確定", "取消", "提交", "下載本章",
    "請先", "登錄", "註冊", "忘記密碼", "會員中心", "我的書架",
    "正在加載", "加載中", "請稍候", "暫無", "評論", "書友",
    "全球降臨", "帶著嫂嫂", "末世種田",
    "第", "章", "回", "節", "頁", "卷", "話",
    "感謝", "打賞", "月票", "推薦票", "收藏", "訂閱",
    "字數", "更新時間", "作者", "分類", "狀態",
    "一秒", "記住", "網址", "手機版", "閱讀",
    "繼續", "點擊", "鼠標", "滾輪", "屏幕",
    "抬頭", "眼前", "身後", "腳下", "心中", "體內",
    "方向", "位置", "距離", "時間", "空間",
    # common grammar/connector words — not real terms
    "時候", "然後", "那么", "當然", "可惜", "此刻", "然而",
    "以下", "與此同時", "沒一會", "天啊", "除此之外",
    "一方面", "另一方面", "實際上", "事實上", "看起來",
    "似乎", "幾乎", "突然", "忽然", "原來", "本來",
    "因為", "所以", "但是", "而且", "並且", "或者",
    "如果", "雖然", "儘管", "無論", "只要", "除非",
    # common measure words and quantity
    "個食物", "塊蛇肉", "點經驗", "經驗值",
    # single characters that are grammar, not terms
    "的", "了", "是", "在", "有", "我", "你", "他", "她",
    "它", "們", "這", "那", "哪", "什", "麼", "怎", "樣",
    "不", "也", "就", "都", "還", "要", "會", "能", "可",
    "以", "已", "經", "來", "去", "上", "下", "裡", "出",
    "入", "進", "到", "說", "看", "聽", "做", "想", "知",
    "道", "見", "給", "把", "被", "讓", "使", "用", "對",
    "於", "與", "和", "或", "從", "而", "但", "因", "所",
    "當", "如", "果", "雖", "然", "可", "是", "為", "比",
    "中", "大", "小", "多", "少", "長", "高", "低", "重",
    "新", "舊", "好", "壞", "美", "醜", "真", "假", "對",
}

# Korean/Hangul noise (for KR source)
_KOREAN_MARKERS = {
    "번역", "수정", "오류", "신고", "투표", "추천", "소장", "책갈피",
    "댓글", "목록", "다음", "이전", "처음", "마지막", "페이지",
}

_CN_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")  # 2-8 CJK chars
_HANGUL_RE = re.compile(r"[\uac00-\ud7af]{2,8}")
_KATAKANA_RE = re.compile(r"[\u30a0-\u30ff]{2,8}")
_HIRAGANA_RE = re.compile(r"[\u3040-\u309f]{2,8}")


def _get_glossary_path(slug: str = "global-descent") -> Path:
    """Get path to glossary.json."""
    try:
        from schema import get_novel_root
        return get_novel_root(slug, check_exists=False) / "glossary" / "glossary.json"
    except ImportError:
        return _PROJECT_ROOT / "novels" / slug / "glossary" / "glossary.json"


@lru_cache(maxsize=8)
def _load_existing_terms(slug: str = "global-descent") -> set[str]:
    """Load ALL existing source terms from glossary.json (cached)."""
    path = _get_glossary_path(slug)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {t["source"] for t in data.get("terms", []) if t.get("source")}
    except Exception:
        return set()


def extract_unknown_terms(
    source_text: str,
    slug: str = "global-descent",
    source_lang: str = "cn",
    min_freq: int = 2,
) -> list[dict[str, Any]]:
    """Extract terms from source that aren't in glossary yet.

    Args:
        source_text: Cleaned source text.
        slug: Novel slug.
        source_lang: 'cn', 'jp', 'kr', 'en'
        min_freq: Minimum occurrences to consider (filter noise).

    Returns:
        [{"term": "黑龍", "freq": 3, "context": "..."}, ...]
    """
    existing = _load_existing_terms(slug)
    noise = _UI_NOISE.copy()

    # Pick regex based on language
    if source_lang == "kr":
        re_term = _HANGUL_RE
        noise |= _KOREAN_MARKERS
    elif source_lang == "jp":
        re_term = re.compile(
            r"[\u3040-\u309f]{3,8}|[\u30a0-\u30ff]{2,8}|[\u4e00-\u9fff]{2,8}"
        )
    else:
        re_term = _CN_RE

    # Extract ALL terms
    all_terms = re_term.findall(source_text)

    # Count frequency
    freq: dict[str, int] = {}
    for term in all_terms:
        if term in existing or term in noise:
            continue
        freq[term] = freq.get(term, 0) + 1

    # Filter by frequency
    candidates = {t for t, c in freq.items() if c >= min_freq}

    # Attach context snippet (first occurrence ±20 chars)
    result = []
    for term in sorted(candidates, key=lambda t: -freq[t]):
        idx = source_text.find(term)
        start = max(0, idx - 15)
        end = min(len(source_text), idx + len(term) + 15)
        context = source_text[start:end].replace("\n", " ")
        result.append({
            "term": term,
            "freq": freq[term],
            "context": context,
        })

    return result


# ── LLM-based translation proposal ────────────────────────────────────

_DISCOVERY_PROMPT = """You are a Chinese→Thai glossary term translator.

For each Chinese term below, propose a Thai translation.
Rules:
- Keep it concise (1-3 Thai words)
- Use natural Thai, not transliteration by default
- If it's a proper name (person/place), use phonetic transliteration
- If it's a game skill/item, translate meaning
- If unsure, provide your best guess with a "?" prefix

Output format:
term | proposed_thai | confidence(high/medium/low) | note

Terms:
{terms}"""


_KR_DISCOVERY_PROMPT = """You are a Korean→Thai glossary term translator.

For each Korean term below, propose a Thai translation.
Rules:
- Keep it concise (1-3 Thai words)
- Proper names → phonetic transliteration
- Items/skills → translate meaning

Output format:
term | proposed_thai | confidence(high/medium/low) | note

Terms:
{terms}"""


def propose_translations(
    candidates: list[dict[str, Any]],
    source_lang: str = "cn",
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Use LLM to propose Thai translations for unknown terms.

    Args:
        candidates: From extract_unknown_terms()
        source_lang: Source language.
        model: Model name for discovery (default: from pipeline config).

    Returns:
        Updated candidates with "proposed_thai" and "confidence" fields.
    """
    if not candidates:
        return candidates

    from pipeline import call_llm

    # Build term list for prompt (max 30 per call to keep prompt short)
    batch_size = 30
    results = []

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        term_lines = []
        for c in batch:
            term_lines.append(f"{c['term']} | context: {c['context']}")

        prompt_text = "\n".join(term_lines)
        prompt = (
            (_KR_DISCOVERY_PROMPT if source_lang == "kr" else _DISCOVERY_PROMPT)
            .format(terms=prompt_text)
        )

        try:
            response, provider, model_name = call_llm(
                prompt=prompt,
                system=None,
                model=model,
                temperature=0.1,
                max_tokens=2000,
            )
        except Exception as e:
            # Fallback: mark all as unknown
            for c in batch:
                c["proposed_thai"] = f"?[error: {str(e)[:40]}]"
                c["confidence"] = "low"
            results.extend(batch)
            continue

        # Parse response
        for line in response.strip().split("\n"):
            line = line.strip()
            if "|" not in line or line.startswith("#") or line.startswith("term"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue
            term = parts[0]
            proposed = parts[1]
            confidence = parts[2] if len(parts) > 2 else "medium"
            note = parts[3] if len(parts) > 3 else ""

            # Find matching candidate and update
            for c in batch:
                if c["term"] == term:
                    c["proposed_thai"] = proposed
                    c["confidence"] = confidence
                    c["note"] = note
                    break

        results.extend(batch)

    return results


# ── Save discovered terms to glossary ─────────────────────────────────

def save_discovered_terms(
    discovered: list[dict[str, Any]],
    slug: str = "global-descent",
) -> int:
    """Save auto-discovered terms to glossary.json.

    Only saves terms with proposed_thai and confidence != "?".

    Returns:
        Number of terms saved.
    """
    path = _get_glossary_path(slug)
    if not path.exists():
        return 0

    # Load existing
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        terms = data.get("terms", [])
    except Exception:
        terms = []

    existing_sources = {t["source"] for t in terms if t.get("source")}
    saved = 0

    for c in discovered:
        proposed = c.get("proposed_thai", "")
        if not proposed or proposed.startswith("?"):
            continue

        term = c["term"]
        if term in existing_sources:
            continue  # Already in glossary, skip

        new_entry = {
            "source": term,
            "thai": proposed.lstrip("?").strip(),
            "category": "auto_discovered",
            "priority": 3,
            "lock": "auto",
            "verified": False,
            "explanation": c.get("note", ""),
            "notes": f"auto_discovered (freq={c['freq']}, confidence={c.get('confidence', 'medium')})",
        }
        terms.append(new_entry)
        existing_sources.add(term)
        saved += 1

    if saved > 0:
        data = {"terms": terms}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        # Clear cache
        _load_existing_terms.cache_clear()

    return saved


# ── One-shot pipeline hook ────────────────────────────────────────────

def discover_and_save(
    source_text: str,
    slug: str = "global-descent",
    source_lang: str = "cn",
    discovery_model: str | None = None,
) -> dict[str, Any]:
    """Full discovery pipeline: extract → propose → save.

    Called from pipeline.py after Station 6.75.

    Returns:
        {"discovered": N, "saved": N, "terms": [...]}
    """
    candidates = extract_unknown_terms(source_text, slug, source_lang, min_freq=2)
    if not candidates:
        return {"discovered": 0, "saved": 0, "terms": []}

    proposed = propose_translations(candidates, source_lang, discovery_model)
    saved = save_discovered_terms(proposed, slug)

    return {
        "discovered": len(candidates),
        "saved": saved,
        "terms": [{"term": c["term"], "thai": c.get("proposed_thai", "?"), "confidence": c.get("confidence", "low")}
                  for c in proposed[:10]],  # Top 10 for display
    }
