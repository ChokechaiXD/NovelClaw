"""LLM output parser for NovelClaw translation results."""

from __future__ import annotations

import re


def parse_output(output: str, ch_num: int) -> list[str]:
    """Parse LLM plain text into paragraph strings."""
    output = re.sub(r"^```[A-Za-z0-9_-]*\s*\n?", "", output.strip())
    output = re.sub(r"\n?```\s*$", "", output)
    output = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", output)
    output = output.replace("\r\n", "\n")
    paragraphs = re.split(r"\n\n+", output.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    mixed = []
    for p in paragraphs:
        has_quote = '"' in p or "\u201c" in p or "\u201d" in p
        has_non_quote_text = bool(re.sub(r'[\s"\u201c\u201d\u300c\u300d]', "", p))
        if has_quote and has_non_quote_text and "\n" in p:
            lines = [line.strip() for line in p.split("\n") if line.strip()]
            mixed.extend(lines)
        else:
            mixed.append(p)
    paragraphs = mixed

    if len(paragraphs) <= 2 and any(len(p) > 2000 for p in paragraphs):
        giant = paragraphs[0] if paragraphs else ""
        parts = re.split(r"(?<=[.!?。！？])\s*|\n", giant)
        paragraphs = [p.strip() for p in parts if len(p.strip()) > 10]

    if not paragraphs:
        raise ValueError(f"Empty LLM output for ch {ch_num}")

    return paragraphs
