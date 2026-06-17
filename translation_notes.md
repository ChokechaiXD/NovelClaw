# Translation Notes: Chapter 131

This document outlines key glossary decisions, source file indexing discrepancies, and workflow insights discovered during the translation of Chapter 131 (`0131.json` from `source/0133.md`).

---

## 1. The Source File Naming Shift (Critical Finding)

During this task, a significant file name offset was identified between the `chapters/source/` markdown files and the output `chapters/*.json` translated files:

*   **The Cause:** `0128.md` is missing from `chapters/source/`.
*   **The Shift:** Because of the missing source file, the translation pipeline has shifted all source files starting from `0129.md` onwards by -1 index:
    *   `source/0129.md` (`第129章`) $\rightarrow$ translated to `0128.json` (Chapter 128)
    *   `source/0130.md` (`第130章`) $\rightarrow$ translated to `0129.json` (Chapter 129)
    *   `source/0131.md` (`第131章`) $\rightarrow$ translated to `0130.json` (Chapter 130)
*   **Duplicate Source Alert:** `source/0131.md` and `source/0132.md` contain the **exact same Chinese content** (Chapter 130: 亵渎女神，恶魔瑟芬妮亚).
*   **Resolution for Chapter 131:**
    *   To translate Chapter 131 (`0131.json`), the correct source file to use is **`source/0133.md`** (`第133章 那么，代价是什么呢？`).
    *   If `0132.md` had been translated, it would have resulted in a duplicate of Chapter 130.

---

## 2. Glossary Mappings & Character Consistencies

The following terms were aligned with previous translations (`0129.json` and `0130.json`) to guarantee 100% vocabulary coherence:

### Main Faction & Characters
*   `曹星` $\rightarrow$ `เฉาซิง`
*   `柳慕雪` $\rightarrow$ `หลิวมู่เสวี่ย`
*   `姬心月` $\rightarrow$ `จีซินเยว่` (aligned with chapter 130)
*   `蕾妮丝·鹰眼` $\rightarrow$ `เลนนิส ฮอว์อาย` (short name: `เลนนิส`)
*   `阿萨姆` $\rightarrow$ `อาซัม`
*   `安德鲁` $\rightarrow$ `แอนดรูว์`
*   `莎拉` $\rightarrow$ `ซาร่า`
*   `布隆` $\rightarrow$ `บรูน` (aligned with chapter 130)
*   `希儿妲` $\rightarrow$ `ฮิลด้า` (aligned with chapter 130)

### Monsters & Bosses
*   `噬魂怪` $\rightarrow$ `ผีสิง` (retained from Chapter 130's translation instead of a literal translation like *สัตว์ประหลาดกินวิญญาณ*)
*   `噬魂恶魔` $\rightarrow$ `อสูรสะกดวิญญาณ`
*   `瑟芬妮亚·维利亚姆斯` $\rightarrow$ `เซฟีเนีย วิลเลียมส์` (or simply `เซฟีเนีย`)

### Locations & Items
*   `卡莎大教堂` $\rightarrow$ `มหาวิหารคาซ่า`
*   `巴拉丁公爵` $\rightarrow$ `ดยุคบาลาดิน`
*   `石符` $\rightarrow$ `แผ่นหินสลัก` (stone talisman)
*   `马格戴尔` $\rightarrow$ `แม็กแดร์` (the legendary sword *Magdaer* from Guild Wars lore)
*   `克米尔女神` $\rightarrow$ `เทพีคอร์เมียร์` (the Goddess *Kormir* from Guild Wars)

### Skills & Stats
*   `极光骑士` $\rightarrow$ `อัศวินแสงออโรร่า`
*   `枭兽形态` $\rightarrow$ `ร่างนกเค้าแมว` (Owlbear/Moonkin form, retained from Chapter 129)
*   `月火术` $\rightarrow$ `เพลิงจันทรา`
*   `星火术` $\rightarrow$ `เพลิงดารา`
*   `星界沟通` $\rightarrow$ `สื่อสารดวงดาว`
*   `永恒之力` $\rightarrow$ `พลังนิรันดร์`
*   `圣愈术` $\rightarrow$ `เวทรักษาศักดิ์สิทธิ์`
*   `魅影无形` $\rightarrow$ `เงาไร้ตัวตน`
*   `致碍之匕` $\rightarrow$ `กริชขัดขวาง`
*   `恐惧尖啸` $\rightarrow$ `เสียงกรีดร้องตื่นตระหนก`
*   `灵魂尖啸` $\rightarrow$ `เสียงกรีดร้องวิญญาณ`
*   `恩赐解脱` $\rightarrow$ `ปลดปล่อยการุณย์` (Phantom Assassin's *Coup de Grace* ability)

---

## 3. Formatting & Schema Highlights (NovelClaw v3 Pydantic)

1.  **Language and Quotes (`lang: "th"`):**
    *   Since the target chapter was marked as `"lang": "th"`, the dialogue block validator expects Thai curly quotes `“` and `”` rather than Chinese brackets `「` and `」`.
    *   Straight ASCII double quotes (`"`) are strictly rejected by the validator to prevent formatting degradation.
2.  **Narration/Dialogue Separation:**
    *   Sentences containing both narrative actions and dialogue (e.g., `曹星惊呀道：“...”`) are split into distinct `narration` and `dialogue` blocks to fit the strict rendering structure of the web reader.
3.  **WoW Meme Retention:**
    *   The iconic line `“แล้วกูลแดน... สิ่งแลกเปลี่ยนคืออะไรล่ะ?”` (Gul'dan, what must we give in return?) was kept intact to preserve the author's subtle humor and pop-culture easter eggs.

---

## 4. Verification Check

*   **Pydantic validation:** Ran successfully on the generated `0131.json`.
*   **Search Re-indexing:** Executed `python tools/chapter_search.py index` to rebuild the FTS5 sqlite database, confirming 103 active chapters.
*   **Dev server state:** Restarted and listening on `http://localhost:4173/`.
