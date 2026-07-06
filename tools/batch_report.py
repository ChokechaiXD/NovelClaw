#!/usr/bin/env python
"""Summarize translated chapter quality records for a chapter range."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def ratio(out: int, src: int) -> float | None:
    return round(out / src, 3) if src else None


def warn_flags(q: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    length = q.get("lengthRatio") or 0
    if length < 0.85:
        flags.append("length_fail")
    elif length < 0.95:
        flags.append("length_low")

    structure = q.get("structure") or {}
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
    q = data.get("qualityRecord") or {}
    structure = q.get("structure") or {}
    src = structure.get("source") or {}
    out = structure.get("output") or {}
    flags = warn_flags(q)
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
