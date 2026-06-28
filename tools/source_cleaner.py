"""Source text cleanup and lightweight noise checks for translation input."""

from __future__ import annotations

import re
from dataclasses import dataclass


_SOURCE_ARTIFACT_RE = re.compile(
    r"(?:ขอบคุณ|感谢|หน้าที่|上一頁|下一頁|หน้าแรก|ลงทะเบียน|สมัครสมาชิก)"
    r"|(?:Loading|กำลังโหลด)"
)

_READER_NOISE_RE = re.compile(
    r"(?:天天看的|看這個養你|求订阅|求訂閱|求追读|求追讀|月票|推薦票|推荐票|打賞|打赏|收藏|評論|评论|書友|书友)"
)

_CHAPTER_HEADING_RE = re.compile(r"^第[一二三四五六七八九十百千零\d]+章")
_TRAILING_CITATION_RE = re.compile(r"([！？。，；：…—])([」』”\"]?)\s*\d{1,4}(?=\s|$)")
_SHORT_NON_STORY_LINE_RE = re.compile(r"^[^\n\u4e00-\u9fff\u0e00-\u0e7f]{1,40}$", re.MULTILINE)


@dataclass(frozen=True)
class SourceNoiseIssue:
    kind: str
    line: int
    text: str

    def as_dict(self) -> dict[str, str | int]:
        return {"kind": self.kind, "line": self.line, "text": self.text}


def _is_preface_line(line: str) -> bool:
    stripped = line.strip()
    return (
        stripped == ""
        or stripped.startswith("#")
        or "全球降臨" in stripped
        or bool(_CHAPTER_HEADING_RE.match(stripped))
        or bool(_SOURCE_ARTIFACT_RE.search(stripped))
        or bool(_SHORT_NON_STORY_LINE_RE.match(stripped))
    )


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    return bool(_SOURCE_ARTIFACT_RE.search(stripped) or _READER_NOISE_RE.search(stripped))


def clean_source(raw: str) -> str:
    """Remove source-site artifacts while preserving actual story paragraphs."""
    body = raw.split("\n---\n", 1)[0]
    lines = body.splitlines()
    out: list[str] = []
    in_body = False

    for line in lines:
        stripped = line.strip()
        if not in_body:
            if _is_preface_line(stripped):
                continue
            in_body = True

        if _is_noise_line(stripped):
            continue
        out.append(line)

    text = "\n".join(out)
    text = _TRAILING_CITATION_RE.sub(r"\1\2", text)
    text = _SHORT_NON_STORY_LINE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def find_source_noise(text: str) -> list[dict[str, str | int]]:
    """Return likely remaining source artifacts for tests and diagnostics."""
    issues: list[SourceNoiseIssue] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if _TRAILING_CITATION_RE.search(stripped):
            issues.append(SourceNoiseIssue("trailing_citation", line_no, stripped))
        if _SOURCE_ARTIFACT_RE.search(stripped):
            issues.append(SourceNoiseIssue("site_artifact", line_no, stripped))
        if _READER_NOISE_RE.search(stripped):
            issues.append(SourceNoiseIssue("reader_noise", line_no, stripped))
    return [issue.as_dict() for issue in issues]
