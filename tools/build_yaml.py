"""Build glossary.yml from layered Markdown glossary files.

Input files, in priority order:
    novels/<slug>/glossary/locked.md     -> lock=locked, priority=1
    novels/<slug>/glossary/reference.md  -> lock=reference, priority=2
    novels/<slug>/glossary/auto.md       -> lock=auto, priority=3

Output:
    novels/<slug>/glossary/glossary.yml

The generated YAML is consumed by tools/glossary.py. Edit the Markdown source
files, then run this script to regenerate the YAML snapshot.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOVELS_DIR = PROJECT_ROOT / "novels"

LAYERS = [
    ("locked.md", "locked", 1),
    ("reference.md", "reference", 2),
    ("auto.md", "auto", 3),
]

# Terms that are generic/common vocabulary — an LLM can translate these
# naturally without glossary help. Rejecting them reduces prompt bloat.
GENERIC_TERMS: set[str] = {
    "之",
    "人",
    "传",
    "光",
    "兽",
    "冥",
    "冰",
    "刃",
    "剑",
    "力",
    "古",
    "圣",
    "塔",
    "宝",
    "寒",
    "小",
    "屠",
    "山",
    "巨",
    "弓",
    "影",
    "战",
    "星",
    "晶",
    "暗",
    "月",
    "木",
    "术",
    "机",
    "极",
    "水",
    "法",
    "湖",
    "源",
    "火",
    "灰",
    "灵",
    "狂",
    "王",
    "甲",
    "白",
    "石",
    "祖",
    "神",
    "秘",
    "箭",
    "精",
    "紫",
    "红",
    "绿",
    "蓝",
    "蛇",
    "血",
    "象",
    "赤",
    "酒",
    "醋",
    "金",
    "钢",
    "铁",
    "铜",
    "银",
    "锋",
    "门",
    "闪",
    "雪",
    "霜",
    "风",
    "鬼",
    "魁",
    "魂",
    "魔",
    "鱼",
    "鲜",
    "鹰",
    "黑",
    "龙",
    "上古",
    "中心",
    "丝线",
    "丧钟",
    "传说",
    "传说级",
    "光明",
    "黑暗",
    "森林",
    "闪电",
    "风暴",
    "火焰",
    "战争",
    "宁静",
    "虚无",
    "炼狱",
    "王者",
    "勇者",
    "圣者",
    "骑士",
    "战士",
    "普通",
    "稀有",
    "史诗",
    "神器",
    "凡品",
    "良品",
    "极品",
    "体力",
    "经验",
    "血量",
    "气血",
    "力量",
    "敏捷",
    "智力",
    "精神",
    "元素",
    "冰霜",
    "自然",
    "血液",
    "血统",
    "魔女",
    "悲鸣",
    "霜月",
    "决意",
    "钟声",
    "花香",
    "华丽",
    "祭坛",
    "洞穴",
    "山脉",
    "平原",
    "湖泊",
    "河水",
    "山峰",
    "山谷",
    "悬崖",
    "水流",
    "木材",
    "石块",
    "尸体",
    "水井",
    "领地",
    "领民",
    "先祖",
    "古老",
    "湖水",
    "湖面",
    "火光",
    "锁链",
    "铁器",
    "菜刀",
    "裤腿",
    "薄冰",
    "花纹",
    "松树",
    "白桦树",
    "苹果树",
    "一阶",
    "二阶",
    "三阶",
    "四阶",
    "五阶",
    "六阶",
    "七阶",
    "八阶",
    "九阶",
    "十阶",
    "一阶精英",
    "二阶精英级",
    "二阶头目级",
    "三阶精英",
    "精英",
    "头目",
    "头目级",
    "护卫",
    "随从",
    "暴擊率",
    "精準度",
    "飽食度",
    "侦察",
    "锻造",
    "采矿",
    "采药",
    "烹饪",
    "钓鱼",
    "皮肤",
    "骨骼",
    "皮毛",
    "皮革",
    "兽皮",
    "兽骨",
    "兽肉",
    "金币",
    "银币",
    "铜币",
    "钱币",
    "苹果",
    "箭矢",
    "匕首",
    "战刀",
    "巨剑",
    "战甲",
    "锁甲",
    "皮甲",
    "布甲",
    "盾牌",
    "长剑",
    "短剑",
    "大剑",
    "法杖",
    "药水",
    "药剂",
    "卷轴",
    "图纸",
    "配方",
    "兄弟",
    "姐妹",
    "父母",
    "孩子",
    "朋友",
    "敌人",
    "伙伴",
    "早晨",
    "中午",
    "傍晚",
    "夜晚",
    "昨天",
    "今天",
    "明天",
    "这里",
    "那里",
    "哪里",
    "因为",
    "所以",
    "但是",
    "而且",
    "然后",
    "虽然",
    "如果",
    "或者",
    "还是",
    "只是",
    "是的",
    "不是",
    "没有",
    "可以",
    "可能",
    "应该",
    "必须",
    "请",
    "谢谢",
    "对不起",
    "你好",
    "再见",
    "火之",
    "冰火",
    "暗影",
    "魔能",
    "神阶",
    "六芒星",
    "黑狮",
    "正月初一",
    "端午",
    "编辑",
    "编辑大大",
    "茶",
    "食物",
    "英雄",
    "怪物",
    "野兽",
    "恶魔",
    "天使",
    "亡灵",
    # Generic vocabulary (added 2026-06 — an LLM translates these naturally)
    "专精",
    "侏儒",
    "先锋",
    "內測",
    "公測",
    "冻结",
    "剧毒",
    "加點",
    "原住居民",
    "原住居民/幸存者",
    "合金",
    "嗜血",
    "坚冰",
    "冒险者",
    "战斗",
    "死亡",
    "灵魂",
    "狂热",
    "白金",
    "白银",
    "寒冷",
    "寒气",
    "山神",
    "巅峰",
    "打赏",
    "极地",
    "树脂",
    "炼金学",
    "庇護所",
    "新手保護期",
    "巔峰",
}
SINGLE_CHAR_RE = re.compile(r"^[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]$")


def should_reject_auto_term(source: str, _category: str) -> bool:
    """Return True if an auto-detected term should not go into the glossary.

    Rules:
    1. Single CJK character → reject (basic vocabulary, not a proper noun)
    2. Known generic/commons vocabulary → reject
    """
    if SINGLE_CHAR_RE.match(source):
        return True
    return source in GENERIC_TERMS


def _split_table_row(line: str) -> list[str]:
    """Split a Markdown table row into trimmed cells."""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _looks_like_separator(cells: list[str]) -> bool:
    return bool(cells) and all(set(cell.replace(":", "").strip()) <= {"-"} for cell in cells)


def _looks_like_header(cells: list[str]) -> bool:
    lowered = [cell.lower() for cell in cells]
    return "source" in lowered and "thai" in lowered


def _parse_priority_and_notes(extra_cells: list[str], default_priority: int) -> tuple[int, str]:
    priority = default_priority
    notes_cells = list(extra_cells)

    if notes_cells:
        first = notes_cells[0].strip()
        if first.isdigit():
            priority = int(first)
            notes_cells = notes_cells[1:]

    return priority, " | ".join(cell for cell in notes_cells if cell).strip()


def parse_markdown_terms(path: Path, lock: str, default_priority: int) -> list[dict[str, object]]:
    """Parse glossary terms from Markdown table rows.

    The existing glossary Markdown files are not perfectly uniform. This parser
    accepts both of these shapes:
        | Source | Thai | Category | Notes |
        | Source | Thai | Category | Priority | Notes |
        | Source | Thai | Category | Priority | Lock | Notes |
    """
    if not path.exists():
        return []

    terms: list[dict[str, object]] = []
    seen_sources: set[str] = set()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        cells = _split_table_row(raw_line)
        if not cells or _looks_like_separator(cells) or _looks_like_header(cells):
            continue
        if len(cells) < 3:
            continue

        source = cells[0].strip()
        thai = cells[1].strip()
        category = cells[2].strip() or "ทั่วไป"
        if not source or not thai or source in seen_sources:
            continue

        extra = cells[3:]
        priority, notes = _parse_priority_and_notes(extra, default_priority)

        explicit_lock = lock
        if len(extra) >= 2 and extra[1].strip() in {"locked", "reference", "auto"}:
            explicit_lock = extra[1].strip()
            notes = " | ".join(extra[2:]).strip()

        # Auto-reject: skip common/vocabulary-only auto terms
        if explicit_lock == "auto" and should_reject_auto_term(source, category):
            continue

        terms.append(
            {
                "source": source,
                "thai": thai,
                "category": category,
                "priority": priority,
                "lock": explicit_lock,
                "explanation": "",
                "notes": notes,
            }
        )
        seen_sources.add(source)

    return terms


def build_terms(slug: str) -> list[dict[str, object]]:
    glossary_dir = NOVELS_DIR / slug / "glossary"
    all_terms: list[dict[str, object]] = []
    seen_sources: set[str] = set()

    for filename, lock, default_priority in LAYERS:
        for term in parse_markdown_terms(glossary_dir / filename, lock, default_priority):
            source = str(term["source"])
            if source in seen_sources:
                continue
            all_terms.append(term)
            seen_sources.add(source)

    all_terms.sort(key=lambda item: (int(item.get("priority", 3)), str(item.get("source", ""))))
    return all_terms


def write_yaml(slug: str, terms: Iterable[dict[str, object]]) -> Path:
    glossary_dir = NOVELS_DIR / slug / "glossary"
    out_path = glossary_dir / "glossary.yml"
    terms_list = list(terms)

    header = (
        "# Auto-generated by tools/build_yaml.py — DO NOT EDIT BY HAND\n"
        f"# Source: novels/{slug}/glossary/{{locked,reference,auto}}.md\n"
        "# Edit .md, then run `python tools/build_yaml.py --novel " + slug + "` to regenerate.\n"
        f"# Terms: {len(terms_list)}\n\n"
    )
    payload = yaml.safe_dump(
        {"terms": terms_list},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    out_path.write_text(header + payload, encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build glossary.yml from layered Markdown glossary files."
    )
    parser.add_argument("--novel", default="global-descent", help="Novel slug under novels/.")
    args = parser.parse_args()

    novel_root = NOVELS_DIR / args.novel
    if not novel_root.exists():
        raise SystemExit(f"Novel not found: {novel_root}")

    terms = build_terms(args.novel)
    out_path = write_yaml(args.novel, terms)
    print(f"Built {out_path} with {len(terms)} terms")


if __name__ == "__main__":
    main()
