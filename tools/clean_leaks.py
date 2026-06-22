"""
clean_leaks.py — Remove CJK and English leaks from all translated chapters.

This actually modifies the chapter files to clean up remaining 
CJK characters and blacklisted English words.

Usage:
    python tools/clean_leaks.py
    python tools/clean_leaks.py --dry-run  (preview only)
"""

import json, re, sys
from pathlib import Path

NOVEL = Path("novels/global-descent")
CH_DIR = NOVEL / "chapters"

# CJK regex
CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')

# EN blacklist — same as scorer.py
EN_BLACKLIST = {
    "recruiting", "level", "disrespect", "mean", "queen",
    "erupt", "continue", "panic", "momentarily", "hollow",
    "militia", "avatar", "blacklist", "peek",
    "first", "kill", "recruit", "loot", "skill", "quest", "boss",
    "dungeon", "party", "guild", "raid", "tank", "healer",
    "damage", "defense", "attack", "speed",
    "inventory", "equip", "item", "craft",
    "summon", "portal", "shield", "weapon", "armor",
    "pet", "mount", "crystal", "stone", "potion",
    "common", "uncommon", "rare", "epic", "legendary",
    "hybrid", "ancient", "elite", "melee", "ranged",
    "plants", "zombies",
    "recruiting", "level", "disrespect", "mean", "queen",
    "erupt", "continue", "panic", "momentarily", "hollow",
    "militia", "avatar", "blacklist", "peek",
    "buff", "debuff",
}

EN_REPLACEMENTS = {
    "recruiting": "รับสมัคร", "disrespect": "ไม่เคารพ", "mean": "หมายถึง",
    "queen": "ราชินี", "continue": "ต่อไป", "panic": "ตื่นตระหนก",
    "erupt": "ปะทุ", "militia": "กองกำลัง", "avatar": "อวตาร",
    "blacklist": "บัญชีดำ", "peek": "แอบดู", "level": "เลเวล",
    "buff": "บัฟ", "debuff": "ดีบัฟ",
    "first": "แรก", "kill": "ฆ่า", "hollow": "กลวง",
    "momentarily": "ชั่วครู่", "plants": "พืช", "zombies": "ซอมบี้",
    "recruit": "รับสมัคร", "loot": "ของรางวัล",
    "skill": "สกิล", "quest": "เควส", "boss": "บอส",
    "dungeon": "ดันเจี้ยน", "party": "ปาร์ตี้", "guild": "กิลด์",
    "raid": "แรด", "tank": "แทงค์", "healer": "ฮีลเลอร์",
    "damage": "แดเมจ", "defense": "ป้องกัน", "attack": "โจมตี", "speed": "ความเร็ว",
    "inventory": "กระเป๋า", "equip": "สวมใส่", "item": "ไอเทม", "craft": "คราฟต์",
    "summon": "อัญเชิญ", "portal": "ประตูมิติ", "shield": "โล่", "weapon": "อาวุธ", "armor": "เกราะ",
    "pet": "สัตว์เลี้ยง", "mount": "พาหนะ", "crystal": "คริสตัล", "stone": "หิน", "potion": "ยาหยด",
    "common": "ทั่วไป", "uncommon": "ไม่ธรรมดา", "rare": "หายาก", "epic": "มหากาพย์", "legendary": "ตำนาน",
    "hybrid": "ลูกผสม", "ancient": "โบราณ", "elite": "หัวกะทิ", "melee": "ระยะประชิด", "ranged": "ระยะไกล",
}

def clean_paragraph(text: str) -> str:
    """Clean CJK + EN leaks from a paragraph."""
    # Remove CJK chars
    text = CJK_RE.sub("", text)
    # Replace blacklisted EN words (whole word only)
    for word, thai in EN_REPLACEMENTS.items():
        text = re.sub(r'\b' + re.escape(word) + r'\b', thai, text, flags=re.IGNORECASE)
    return text.strip()

def clean_file(json_path: Path, dry_run: bool = False) -> dict:
    """Clean one chapter file. Returns stats."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    stats = {"cn_removed": 0, "en_replaced": 0, "changed": False}

    if data.get("paragraphs"):
        for i, para in enumerate(data["paragraphs"]):
            if para in ("(จบบท)", "(End)", "（終）", "(끝)"):
                continue
            old = para
            # Count CJK
            cn_count = len(CJK_RE.findall(old))
            # Count EN
            en_count = 0
            for word in EN_BLACKLIST:
                en_count += len(re.findall(r'\b' + re.escape(word) + r'\b', old, re.IGNORECASE))
            
            new = clean_paragraph(old)
            if new != old:
                data["paragraphs"][i] = new
                stats["cn_removed"] += cn_count
                stats["en_replaced"] += en_count
                stats["changed"] = True

    elif data.get("blocks"):
        for block in data.get("blocks", []):
            if block.get("type") == "end":
                continue
            text = block.get("text", "")
            if not text:
                continue
            old = text
            cn_count = len(CJK_RE.findall(old))
            en_count = 0
            for word in EN_BLACKLIST:
                en_count += len(re.findall(r'\b' + re.escape(word) + r'\b', old, re.IGNORECASE))
            new = clean_paragraph(old)
            if new != old:
                block["text"] = new
                stats["cn_removed"] += cn_count
                stats["en_replaced"] += en_count
                stats["changed"] = True

    if stats["changed"] and not dry_run:
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return stats

def main():
    dry_run = "--dry-run" in sys.argv

    files = sorted(CH_DIR.glob("*.json"))
    total_cn = 0
    total_en = 0
    changed = 0

    for f in files:
        stats = clean_file(f, dry_run=dry_run)
        if stats["changed"]:
            changed += 1
            total_cn += stats["cn_removed"]
            total_en += stats["en_replaced"]
            if stats["cn_removed"] > 0 or stats["en_replaced"] > 0:
                detail = []
                if stats["cn_removed"] > 0:
                    detail.append(f"{stats['cn_removed']} CN")
                if stats["en_replaced"] > 0:
                    detail.append(f"{stats['en_replaced']} EN")
                print(f"  {f.stem}: {', '.join(detail)}")

    mode = "DRY RUN" if dry_run else "DONE"
    print(f"\n{mode}: {changed} files affected, {total_cn} CJK chars removed, {total_en} EN words replaced")

if __name__ == "__main__":
    main()
