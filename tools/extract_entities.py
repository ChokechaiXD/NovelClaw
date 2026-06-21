"""extract_entities.py — Extract proper nouns from Chinese source text.

CN-to-TH entity extraction using bracket analysis, frequency heuristics,
and glossary cross-reference. Designed for the NovelClaw entity pipeline.

Strategy (no capitalization in CJK):
  1. Extract terms inside 《》【】「」 (brackets signal proper nouns)
  2. Multi-char sequences appearing 3+ times in source (likely named entities)
  3. Terms matching glossary locked/reference tiers
  4. Filter out common vocabulary via generic CN term list

Output: list of {source, context, frequency, bracket_type, in_glossary}
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

# ── Bracket patterns that signal proper nouns ─────────────────────
# 《 》 — book/game/novel titles, proper works
GAME_TITLE_RE = re.compile(r"《([^》]{1,20})》")
# 【 】 — system messages, game notifications, skill names
SYSTEM_BRACKET_RE = re.compile(r"【([^】]{1,20})】")
# 「 」 — dialogue — first word is often a character name
DIALOGUE_RE = re.compile(r"「([^」]{1,60})」")
# 『 』 — Japanese-style emphasis brackets
JP_BRACKET_RE = re.compile(r"『([^』]{1,20})』")

# ── Generic CN words to exclude (not proper nouns) ────────────────
# These are common vocab that LLMs handle fine without glossary entries.
GENERIC_CN = {
    # Common verbs
    "知道", "可以", "没有", "不是", "就是", "这个", "那个", "什么", "怎么", "因为",
    "所以", "但是", "如果", "虽然", "然后", "发现", "看见", "听到", "想到",
    "进入", "离开", "回到", "来到", "打开", "关闭", "开始", "结束", "出现",
    "消失", "增加", "减少", "提升", "下降", "获得", "失去", "使用", "装备",
    "攻击", "防御", "移动", "停止", "继续", "等待", "完成", "失败", "成功",
    "请问", "谢谢", "再见",
    # Common adjectives
    "强大", "弱小", "美丽", "丑陋", "可怕", "安全", "危险", "简单", "困难",
    "普通", "特殊", "重要", "一般", "高级", "低级", "初级", "终极", "超级",
    "巨大", "微小", "古老", "年轻", "新的", "旧的",
    # Common nouns (generic)
    "时候", "地方", "世界", "东西", "事情", "问题", "答案", "方法", "原因",
    "结果", "目标", "任务", "系统", "功能", "信息", "数据", "能力", "力量",
    "速度", "方向", "位置", "房间", "建筑", "城市", "国家", "大陆", "天空",
    "大地", "海洋", "森林", "山脉", "河流", "道路", "门口", "角落", "中心",
    "周围", "附近", "前面", "后面", "上面", "下面", "里面", "外面",
    # Common time
    "今天", "明天", "昨天", "早上", "中午", "晚上", "早晨", "傍晚", "深夜",
    "现在", "以前", "以后", "过去", "未来", "瞬间", "片刻",
    # Common quantifiers / pronouns
    "自己", "别人", "大家", "所有", "每个", "任何", "整个", "全部",
    "第一", "第二", "最后", "唯一", "无数", "许多", "大量", "少量",
    # Game mechanics (too generic)
    "等级", "经验", "血量", "魔力", "体力", "力量", "敏捷", "智力",
    "精神", "耐力", "攻击", "防御", "速度", "幸运", "技能", "魔法",
    "装备", "武器", "防具", "饰品", "药水", "卷轴", "金币", "钻石",
    "任务", "副本", "竞技", "排行", "商城", "背包", "仓库",
    # Generic items
    "苹果", "面包", "水", "肉", "石头", "木材", "铁矿", "金币",
    "衣服", "鞋子", "帽子", "戒指", "项链",
    # Basic elements
    "水", "火", "风", "土", "光", "暗", "冰", "雷", "电",
    "元素", "火焰", "冰冻", "雷电", "风暴", "大地",
    # Connected text artifacts
    "版权", "所有", "首发", "小说网", "章节", "字数", "更新",
    "加入书架", "推荐票", "月票", "打赏",
}

# ── CN character ranges (CJK Unified Ideographs) ───────────────────
# Extended to include CJK Extension A for rare characters
CJK_CHAR = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

# Minimum length for a named entity (2 chars minimum for CN proper nouns)
MIN_ENTITY_LEN = 2
MAX_ENTITY_LEN = 12


def _is_generic(term: str) -> bool:
    """Check if a CN term is generic vocabulary (not a proper noun)."""
    if term in GENERIC_CN:
        return True
    # Single characters are too ambiguous
    if len(term) < MIN_ENTITY_LEN:
        return True
    # All common radicals/infrastructure characters
    if all(CJK_CHAR.match(c) is None for c in term):
        return True
    return False


def extract_from_brackets(text: str) -> list[dict[str, Any]]:
    """Extract proper nouns from bracket-marked regions.

    《》 = game/book titles — almost always proper nouns
    【】 = system notifications — often skill/item/notification names
    『』 = Japanese-style emphasis — likely proper nouns
    """
    entities = []
    seen = set()

    for pattern, bracket_type in [
        (GAME_TITLE_RE, "game_title"),
        (SYSTEM_BRACKET_RE, "system"),
        (JP_BRACKET_RE, "jp_bracket"),
    ]:
        for match in pattern.finditer(text):
            term = match.group(1).strip()
            if term and term not in seen and not _is_generic(term):
                seen.add(term)
                entities.append({
                    "source": term,
                    "context": text[max(0, match.start() - 20): match.end() + 20],
                    "frequency": 1,
                    "bracket_type": bracket_type,
                    "in_glossary": False,
                })

    return entities


def extract_dialogue_speakers(text: str) -> list[dict[str, Any]]:
    """Extract likely speaker names from dialogue brackets.

    In CN web novels, the first 1-4 CJK chars inside 「」 are often
    the speaker name. This is heuristic — some dialogues don't have
    explicit speakers.
    """
    entities = []
    seen = set()

    for match in DIALOGUE_RE.finditer(text):
        content = match.group(1).strip()
        if not content:
            continue
        # Try to extract first 2-4 CJK chars as potential speaker
        chars = []
        for c in content:
            if CJK_CHAR.match(c):
                chars.append(c)
            else:
                break
        if 2 <= len(chars) <= 4:
            candidate = "".join(chars)
            if candidate not in seen and not _is_generic(candidate):
                seen.add(candidate)
                entities.append({
                    "source": candidate,
                    "context": f"「{content[:40]}」",
                    "frequency": 1,
                    "bracket_type": "dialogue",
                    "in_glossary": False,
                })

    return entities


def extract_frequent_terms(text: str, min_freq: int = 3) -> list[dict[str, Any]]:
    """Extract multi-char CN sequences appearing frequently.

    Frequency is a weak signal — common words also appear frequently.
    This is filtered through _is_generic() to remove common vocab.
    """
    # Find all 2-12 char CN sequences
    terms = CJK_CHAR.findall(text)
    # Build n-grams of length 2-6
    counter: Counter = Counter()
    for n in range(2, min(7, max(2, len(terms) // 10 + 2))):
        for i in range(len(terms) - n + 1):
            ngram = "".join(terms[i: i + n])
            if not _is_generic(ngram):
                counter[ngram] += 1

    entities = []
    seen = set()
    for term, freq in counter.most_common(50):
        if freq < min_freq:
            break
        if term in seen:
            continue
        seen.add(term)
        entities.append({
            "source": term,
            "context": "",
            "frequency": freq,
            "bracket_type": "frequent",
            "in_glossary": False,
        })

    return entities


def cross_reference_glossary(
    entities: list[dict[str, Any]],
    glossary_terms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mark entities found in glossary and add priority/translation."""
    glossary_map = {t["source"]: t for t in glossary_terms}
    for ent in entities:
        if ent["source"] in glossary_map:
            ent["in_glossary"] = True
            g = glossary_map[ent["source"]]
            ent["thai"] = g.get("thai", "")
            ent["priority"] = g.get("priority", 3)
            ent["lock"] = g.get("lock", "reference")
    return entities


def extract_entities(
    text: str,
    glossary_terms: list[dict[str, Any]] | None = None,
    min_freq: int = 3,
) -> list[dict[str, Any]]:
    """Full entity extraction pipeline for CN text.

    Merges bracket entities + dialogue speakers + frequency-based terms,
    deduplicates, cross-references with glossary, and sorts by certainty.
    """
    all_entities: list[dict[str, Any]] = []
    seen_sources = set()

    # 1. Bracket entities (highest certainty)
    for ent in extract_from_brackets(text):
        if ent["source"] not in seen_sources:
            seen_sources.add(ent["source"])
            all_entities.append(ent)

    # 2. Dialogue speakers (medium certainty)
    for ent in extract_dialogue_speakers(text):
        if ent["source"] not in seen_sources:
            seen_sources.add(ent["source"])
            all_entities.append(ent)

    # 3. Frequent terms (weakest signal — only if not already found)
    for ent in extract_frequent_terms(text, min_freq=min_freq):
        if ent["source"] not in seen_sources:
            seen_sources.add(ent["source"])
            all_entities.append(ent)

    # 4. Cross-reference with glossary
    if glossary_terms:
        all_entities = cross_reference_glossary(all_entities, glossary_terms)

    # Sort: glossary-locked first, then bracket entities, then frequency
    def sort_key(e: dict) -> tuple:
        priority = e.get("priority", 999)
        is_glossary = 0 if e["in_glossary"] else 1
        is_bracket = 0 if e.get("bracket_type") in ("game_title", "system", "jp_bracket") else 1
        freq = -(e.get("frequency", 1))
        return (is_glossary, priority, is_bracket, freq)

    all_entities.sort(key=sort_key)
    return all_entities


def entity_to_placeholder(entity_source: str) -> str:
    """Convert an entity to a deterministic SHA-256 placeholder.

    Format: __ENT_<first_8_hex_chars>__

    Deterministic: same entity text always produces same placeholder.
    """
    h = hashlib.sha256(entity_source.encode("utf-8")).hexdigest()[:8]
    return f"__ENT_{h}__"


PLACEHOLDER_RE = re.compile(r"__ENT_[a-f0-9]{8}__")


def replace_entities_with_placeholders(
    text: str,
    entities: list[dict[str, Any]],
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Replace entity occurrences in text with placeholders.

    Returns:
        (modified_text, placeholder_map)
        placeholder_map = {placeholder: {source, thai_or_empty}}
    """
    placeholder_map: dict[str, dict[str, Any]] = {}
    result = text

    for ent in entities:
        source = ent["source"]
        placeholder = entity_to_placeholder(source)
        placeholder_map[placeholder] = {
            "source": source,
            "thai": ent.get("thai", ""),
            "lock": ent.get("lock", "auto"),
            "priority": ent.get("priority", 3),
        }
        # Replace all occurrences (CN text → placeholder)
        result = result.replace(source, placeholder)

    return result, placeholder_map


def restore_entities_from_map(
    text: str,
    placeholder_map: dict[str, dict[str, Any]],
) -> str:
    """Restore placeholders back to original entity text in LLM output.

    If a Thai translation exists in glossary, use that instead of
    the original CN entity text.
    """
    result = text
    for placeholder, info in placeholder_map.items():
        # Use glossary Thai if available, else keep CN source
        replacement = info.get("thai") or info["source"]
        result = result.replace(placeholder, replacement)
    return result



def verify_no_leaked_entities(
    text: str,
    placeholder_map: dict[str, dict[str, Any]],
) -> list[str]:
    """Check that no original entity text leaked through untranslated.

    Returns list of leaked entity sources found in text.
    """
    leaked = []
    for info in placeholder_map.values():
        source = info["source"]
        if source in text:
            leaked.append(source)
    return leaked


def entity_extraction_pipeline(
    chapter_num: int,
    source_text: str,
    glossary_terms: list[dict[str, Any]] | None = None,
    min_freq: int = 3,
) -> dict[str, Any]:
    """Run full entity pipeline for a single chapter.

    Returns dict with:
      - entities: list of extracted entities
      - placeheld_text: source text with entities replaced
      - placeholder_map: {placeholder: entity_info}
      - count: number of entities found
    """
    entities = extract_entities(source_text, glossary_terms, min_freq=min_freq)

    # Only placeholder-ify entities NOT already in glossary with locked tier
    # (those are handled by prompt injection, not placeholder replacement)
    to_replace = []
    for ent in entities:
        if ent.get("lock") == "locked":
            continue  # glossary locked terms still injected via prompt
        to_replace.append(ent)

    placeheld_text, placeholder_map = replace_entities_with_placeholders(
        source_text, to_replace
    )

    return {
        "chapter": chapter_num,
        "entities": entities,
        "placeheld_text": placeheld_text,
        "placeholder_map": placeholder_map,
        "count": len(entities),
        "replaced_count": len(to_replace),
    }
