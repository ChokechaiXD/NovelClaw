# -*- coding: utf-8 -*-
"""R2 APPLY: fix CJK leak (ch1/81/155) + glossary.json -> locked.md. Data-only, no Go."""
import io, json, os, re, collections, sys

sys.stdout.reconfigure(encoding="utf-8")
BASE = r"C:/Users/BlankScreen/Workspace/NovelClaw/novels/global-descent"
CH = os.path.join(BASE, "chapters")
GL = os.path.join(BASE, "glossary")

def load(p):
    return json.load(io.open(p, encoding="utf-8"))

def save(p, obj):
    json.dump(obj, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def txt(p):
    return p if isinstance(p, str) else p.get("text", "")

han = re.compile(r'[\u4e00-\u9fff]')

# ---------- 1) CJK LEAK FIX ----------
# Map: chapter -> {swapped paragraph index -> new full text (translated from CN source)}
CH1_FIX = {
    32: '"น่าเสียดาย คุณพี่ใหญ่ของฉันไม่มีวาสนาได้เสวยสุขเช่นนี้"',
    35: '"อาซิง คุณจะไปไหน?"',
    41: 'เฉาซิงอยู่ตัวคนเดียว ไม่มีใครพึ่งพิง ในเมืองเซียนเจียงแบบนี้ แค่มีชีวิตรอดก็ยากมากแล้ว',
    53: '"ฉันบอกแล้ว ว่าตอนแรกที่ฉันยอมแต่งเข้าตระกูลหย่งเซิ่ง ก็เพราะพวกคุณเป็นคนขอ แต่ตอนนี้เฉินเจียงตายไปแล้ว ฉันกับเขาก็ไม่มีความเกี่ยวข้องกันอีก"',
    64: 'เฉินเจียง ประธานกรรมการของกลุ่มหย่งเซิ่ง และเป็นพี่ชายของเฉาซิง ก็เป็นหนึ่งในนั้น',
    83: '"ดังนั้น ขออวยพรให้ทุกคนในโลกใหม่นี้พยายามมีชีวิตรอดและสร้างชีวิตที่ดี..."',
    104: '"ขอให้ผู้รอดชีวิตทุกคนรีบเลือกระบบอาชีพของตัวเองให้เร็วที่สุด"',
    106: 'ดวงตาของเฉาซิงวาบด้วยความดีใจ',
    109: 'แน่นอน เฉาซิงรู้ว่าทั้งห้าอาชีพนี้ในระยะแรกแทบไม่มีพลังต่อสู้',
    110: 'เช่น ช่างกลเหล็กน้ำแข็ง ในระยะแรกจะมีเพียงทักษะอัญเชิญหุ่นยนต์ระเบิดขนาดเล็ก ซึ่งพลังทำลายล้างยังสู้ประทัดที่เราใช้ระเบิดส้วมตอนเด็กไม่ได้',
    119: '"เข้าใจแล้ว เกมนี้มีโหมดเอาชีวิตรอดแบบครอบครัว เพื่อให้ผู้รอดชีวิตอย่างพวกเราแบ่งงานกันทำตามอาชีพ ผ่านช่วงต้น กลาง ปลายได้อย่างปลอดภัย แล้วค่อยใช้ชีวิตได้ดีขึ้น"',
    125: 'งั้น...ควรเลือกอาชีพอะไรดี?',
    126: 'หลังจากครุ่นคิดอยู่ครู่หนึ่ง เฉาซิงก็เลือก "จอมเวทน้ำแข็ง" ตรง ๆ',
    128: '"ยินดีด้วย! คุณเลือกอาชีพ "จอมเวทน้ำแข็ง" สำเร็จ ค่าความเข้ากันของธาตุถูกปลดล็อก ความต้านทานความหนาวเพิ่มขึ้นเล็กน้อย อุปกรณ์เริ่มต้นถูกใส่ในกล่องเก็บของแล้ว"',
}
CH81_FIX = {
    152: '【เกราะ: 2',
}
CH155_FIX = {
    12: '"ถึงตอนนั้น กองอัศวินและกองทัพธุดงค์ของอาณาจักรผลึกน้ำแข็ง จะทำลายฐานที่มั่นของพวกเจ้าทีละแห่ง และศพของพวกเจ้าพวกลัทธินอกรีตจะถูกแขวนประจานบนกำแพงเมืองให้หมด!"',
    13: 'เฉาซิงถามด้วยความสนใจ "กองอัศวินกับกองทัพธุดงค์แข็งแกร่งมากเลยเหรอ?"',
    16: '"บวกกับกองทัพธุดงค์ จะกวาดล้างพวกเจ้าพวกลัทธินอกรีตให้สิ้นซากได้ในคราวเดียว!"',
}

def apply_th_fixes(n, fixes):
    p = os.path.join(CH, f"{n:04d}.th.json")
    data = load(p)
    paras = data["paragraphs"]
    before = sum(len(han.findall(txt(t))) for t in paras)
    for idx, new in fixes.items():
        if han.search(txt(paras[idx - 1])):
            paras[idx - 1] = new
    after = sum(len(han.findall(txt(t))) for t in paras)
    save(p, data)
    return before, after

cjk_report = {}
for n, fx in [(1, CH1_FIX), (81, CH81_FIX), (155, CH155_FIX)]:
    b, a = apply_th_fixes(n, fx)
    cjk_report[n] = (b, a)
    print(f"CJK ch{n}: {b} -> {a} leaked chars")

# ---------- 2) GLOSSARY.JSON -> LOCKED.MD ----------
# locked.md is source of truth. Only rewrite targets that conflict.
def parse_locked_md():
    d = {}
    for ln in io.open(os.path.join(GL, "locked.md"), encoding="utf-8"):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        parts = [x.strip() for x in s.strip("|").split("|")]
        if len(parts) >= 2 and re.search(r'[\u4e00-\u9fff]', parts[0]):
            d[parts[0]] = parts[1]
    return d

locked = parse_locked_md()
gjp = os.path.join(GL, "glossary.json")
gj = load(gjp)
gj_before = {it["term"]: it.get("target", "") for it in gj}
changed = []
for it in gj:
    term = it["term"]
    if term in locked and it.get("target") != locked[term]:
        old = it.get("target")
        it["target"] = locked[term]
        changed.append((term, old, locked[term]))
save(gjp, gj)
print("\nglossary.json changes:")
for term, old, new in changed:
    print(f"  {term}: {old} -> {new}")
print("  (%d entries changed)" % len(changed))

# yml already agrees with locked (verified in qa_r2_diff). Re-run verification inline:
def parse_gyml():
    d = {}
    cur = None
    for ln in io.open(os.path.join(GL, "glossary.yml"), encoding="utf-8"):
        s = ln.strip()
        if s.startswith("- source:"):
            cur = s[len("- source:"):].strip().strip("'")
        elif s.startswith("thai:") and cur is not None:
            d[cur] = s[len("thai:"):].strip().strip("'")
    return d
gyml = parse_gyml()
yml_conf = [(t, locked[t], gyml[t]) for t in locked if t in gyml and gyml[t] != locked[t]]
print("glossary.yml locked conflicts after json fix:", yml_conf if yml_conf else "none")
