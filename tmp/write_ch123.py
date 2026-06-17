import json, os

data = {
    "schema_version": 2,
    "num": 123,
    "title": "ตอนที่ 123: การค้า กล่องกินปีศาจประหลาด",
    "lang": "th",
    "blocks": [],
    "source": "ch 123",
    "notes": []
}

b = data["blocks"]

# Source: chapters/source/0123.md - "交易,詭異的吞魔之盒"
# 1. Marita apologizes and scolds Yowan
# 2. Cao Xing flatters Marita
# 3. Sells moon essence pearls 2 for 1M crowns
# 4. Sells other items (sticky liquid, candlesticks, amber pebbles, bear paws)
# 5. Browses shop - sees many items
# 6. Buys life potions, pet food, mechanical factory blueprint
# 7. Asks about demon-devouring box - 60K crowns
# 8. Marita explains the demon box
# 9. Cao Xing buys it

b.append({"type": "narration", "text": "原来这个叫做玛丽塔的女人是四阶强者，难怪约万那么害怕她。"})  # placeholder - need translation
