import json, sys

with open("novels/global-descent/chapters/0122.json", "r", encoding="utf-8") as f:
    data = json.load(f)

fixed = 0
for i, blk in enumerate(data["blocks"]):
    txt = blk.get("text", "")
    if blk.get("type") == "dialogu":
        blk["type"] = "dialogue"
        fixed += 1
    if "Continue" in txt:
        txt = txt.replace("Continue", "")
        blk["text"] = txt
        fixed += 1
    if "Again" in txt:
        txt = txt.replace("Again", "")
        blk["text"] = txt
        fixed += 1

with open("novels/global-descent/chapters/0122.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"Done! Fixed {fixed} issues")
sys.stdout.flush()
