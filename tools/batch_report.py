#!/usr/bin/env python
"""Summarize translated chapter quality records for a chapter range."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# ponytail: report-only guard; move to glossary when canonical name registry exists.
NAME_RULES = {
    "曹星": {"expected": "เฉาซิง", "bad": ["อู๋เจียฮุย"]},
    "柳慕雪": {"expected": "หลิวมู่เสวี่ย", "bad": ["หลิ่วมู่เสวี่ย"]},
}

BOILERPLATE_RE = re.compile(r"全球降臨|投票推薦|加入書籤|小說報錯|首次合區|投票|推薦|書籤")
END_MARKER_RE = re.compile(r"^\s*(จบตอน|END)\s*$", re.I)
TITLE_RE = re.compile(r"^\s*(第\d+章|ตอนที่\s*\d+|บทที่\s*\d+)")
DIALOGUE_RE = re.compile(r"[「“\"]")
SYSTEM_RE = re.compile(r"【[^】]+】")


def visible_text(paragraphs: list[Any]) -> str:
    parts = []
    for p in paragraphs:
        parts.append(str(p.get("text", "") if isinstance(p, dict) else p))
    return "\n".join(parts)


def strip_boilerplate(lines: list[str]) -> list[str]:
    return [line for line in lines if not BOILERPLATE_RE.search(line)]


def content_lines(paragraphs: list[Any], *, source: bool = False) -> list[str]:
    lines = [line.strip() for line in visible_text(paragraphs).splitlines() if line.strip()]
    lines = strip_boilerplate(lines)
    return [
        line for line in lines
        if not END_MARKER_RE.match(line) and not TITLE_RE.match(line) and (source or line != "")
    ]


def count_structure(lines: list[str]) -> dict[str, int]:
    return {
        "paragraphCount": len(lines),
        "dialogueCount": sum(1 for line in lines if DIALOGUE_RE.search(line)),
        "systemMarkerCount": sum(len(SYSTEM_RE.findall(line)) for line in lines),
    }


def name_flags(source_text: str, output_text: str) -> list[str]:
    flags = []
    for source, rule in NAME_RULES.items():
        if source not in source_text:
            continue
        expected = rule["expected"]
        if expected not in output_text:
            flags.append(f"name_missing:{source}->{expected}")
        for bad in rule.get("bad", []):
            if bad in output_text:
                flags.append(f"name_bad:{source}->{bad}")
    return flags


def ratio(out: int, src: int) -> float | None:
    return round(out / src, 3) if src else None


def warn_flags(q: dict[str, Any], source_text: str = "", output_text: str = "", structure_override: dict[str, Any] | None = None) -> list[str]:
    flags: list[str] = []
    length = q.get("lengthRatio") or 0
    if length < 0.85:
        flags.append("length_fail")
    elif length < 0.95:
        flags.append("length_low")

    structure = structure_override or q.get("structure") or {}
    src = structure.get("source") or {}
    out = structure.get("output") or {}
    para = ratio(out.get("paragraphCount", 0), src.get("paragraphCount", 0))
    dialog = ratio(out.get("dialogueCount", 0), src.get("dialogueCount", 0))
    system = ratio(out.get("systemMarkerCount", 0), src.get("systemMarkerCount", 0))

    if para is not None and para < 0.65:
        flags.append("paragraph_drift")
    if dialog is not None and dialog < 0.5:
        flags.append("dialogue_drift")
    if system is not None and system < 0.8:
        flags.append("system_drift")
    if q.get("scriptLeaks", 0):
        flags.append("script_leaks")
    if any(a.get("kind") == "fallback" for a in q.get("attempts", [])):
        flags.append("used_fallback")
    flags.extend(name_flags(source_text, output_text))
    return flags


def load_row(chapters_dir: Path, ch: int) -> dict[str, Any]:
    path = chapters_dir / f"{ch:04d}.th.json"
    if not path.exists():
        return {
            "chapter": ch,
            "status": "missing",
            "score": "",
            "passed": False,
            "lengthRatio": "",
            "paragraphRatio": "",
            "dialogueRatio": "",
            "systemRatio": "",
            "paragraphs": 0,
            "model": "",
            "flags": ["missing"],
            "path": str(path),
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    source_path = chapters_dir / f"{ch:04d}.cn.json"
    source_data = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else {}
    source_lines = content_lines(source_data.get("paragraphs") or source_data.get("content") or [], source=True)
    output_lines = content_lines(data.get("paragraphs", []))
    source_text = "\n".join(source_lines)
    output_text = "\n".join(output_lines)

    q = data.get("qualityRecord") or {}
    adjusted_structure = {"source": count_structure(source_lines), "output": count_structure(output_lines)}
    src = adjusted_structure["source"]
    out = adjusted_structure["output"]
    flags = warn_flags(q, source_text, output_text, adjusted_structure)

    return {
        "chapter": ch,
        "status": "review" if flags else "ok",
        "score": q.get("score"),
        "passed": q.get("passed"),
        "lengthRatio": q.get("lengthRatio"),
        "paragraphRatio": ratio(out.get("paragraphCount", 0), src.get("paragraphCount", 0)),
        "dialogueRatio": ratio(out.get("dialogueCount", 0), src.get("dialogueCount", 0)),
        "systemRatio": ratio(out.get("systemMarkerCount", 0), src.get("systemMarkerCount", 0)),
        "paragraphs": len(data.get("paragraphs", [])),
        "model": (data.get("meta") or {}).get("model"),
        "flags": flags,
        "path": str(path),
    }


def markdown(rows: list[dict[str, Any]]) -> str:
    present = [r for r in rows if r["status"] != "missing"]
    scores = [r["score"] for r in present if isinstance(r.get("score"), (int, float))]
    lines = [
        "# Batch Quality Report",
        "",
        f"Chapters: {rows[0]['chapter']}-{rows[-1]['chapter']}" if rows else "Chapters: none",
        f"Present: {len(present)}/{len(rows)}",
        f"Average score: {round(mean(scores), 2) if scores else 'n/a'}",
        "",
        "| Chapter | Status | Score | Len | Para | Dialogue | System | Flags | Model |",
        "|---:|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {chapter} | {status} | {score} | {lengthRatio} | {paragraphRatio} | {dialogueRatio} | {systemRatio} | {flags} | {model} |".format(
                **{**r, "flags": ", ".join(r.get("flags", [])), "model": r.get("model") or ""}
            )
        )
    return "\n".join(lines) + "\n"


def parse_range(value: str) -> tuple[int, int]:
    if "-" in value:
        a, b = value.split("-", 1)
        return int(a), int(b)
    n = int(value)
    return n, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("range", help="chapter or range, e.g. 201-210")
    ap.add_argument("--slug", default="global-descent")
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    start, end = parse_range(args.range)
    chapters_dir = ROOT / "novels" / args.slug / "chapters"
    rows = [load_row(chapters_dir, ch) for ch in range(start, end + 1)]

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"batch-{start:04d}-{end:04d}"
    (out_dir / f"{stem}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(markdown(rows), encoding="utf-8")
    print(out_dir / f"{stem}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
