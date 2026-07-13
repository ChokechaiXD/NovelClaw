"""Source text cleanup and lightweight noise checks for translation input."""

from __future__ import annotations

import re
from dataclasses import dataclass


# ── Exported noise sets (shared with glossary_discovery) ──────────────

UI_NOISE: set[str] = {
    "首頁", "科幻小說", "玄幻小說", "都市言情", "歷史軍事", "遊戲競技",
    "加入書籤", "小說報錯", "投票推薦", "字體", "上一章", "下一章", "目錄",
    "關燈", "開燈", "下載", "客戶端", "手機看書", "繁體", "簡體",
    "上一頁", "下一頁", "返回", "確定", "取消", "提交", "下載本章",
    "請先", "登錄", "註冊", "忘記密碼", "會員中心", "我的書架",
    "正在加載", "加載中", "請稍候", "暫無", "評論", "書友",
    "全球降臨", "帶著嫂嫂", "末世種田",
    "第", "章", "回", "節", "頁", "卷", "話",
    "感謝", "打賞", "月票", "推薦票", "收藏", "訂閱",
    "字數", "更新時間", "作者", "分類", "狀態",
    "一秒", "記住", "網址", "手機版", "閱讀",
    "繼續", "點擊", "鼠標", "滾輪", "屏幕",
    "抬頭", "眼前", "身後", "腳下", "心中", "體內",
    "方向", "位置", "距離", "時間", "空間",
    # common grammar/connector words — not real terms
    "時候", "然後", "那么", "當然", "可惜", "此刻", "然而",
    "以下", "與此同時", "沒一會", "天啊", "除此之外",
    "一方面", "另一方面", "實際上", "事實上", "看起來",
    "似乎", "幾乎", "突然", "忽然", "原來", "本來",
    "因為", "所以", "但是", "而且", "並且", "或者",
    "如果", "雖然", "儘管", "無論", "只要", "除非",
    # common measure words and quantity
    "個食物", "塊蛇肉", "點經驗", "經驗值",
    # single characters that are grammar, not terms
    "的", "了", "是", "在", "有", "我", "你", "他", "她",
    "它", "們", "這", "那", "哪", "什", "麼", "怎", "樣",
    "不", "也", "就", "都", "還", "要", "會", "能", "可",
    "以", "已", "經", "來", "去", "上", "下", "裡", "出",
    "入", "進", "到", "說", "看", "聽", "做", "想", "知",
    "道", "見", "給", "把", "被", "讓", "使", "用", "對",
    "於", "與", "和", "或", "從", "而", "但", "因", "所",
    "當", "如", "果", "雖", "然", "為", "比",
    "中", "大", "小", "多", "少", "長", "高", "低", "重",
    "新", "舊", "好", "壞", "美", "醜", "真", "假",
}

KOREAN_MARKERS: set[str] = {
    "번역", "수정", "오류", "신고", "투표", "추천", "소장", "책갈피",
    "댓글", "목록", "다음", "이전", "처음", "마지막", "페이지",
}

# ── Source-level noise filters (regex) ──────────────────────────────

_SOURCE_ARTIFACT_RE = re.compile(
    r"(?:ขอบคุณ|感谢|หน้าที่|上一頁|下一頁|หน้าแรก|ลงทะเบียน|สมัครสมาชิก)"
    r"|(?:Loading|กำลังโหลด)"
)

_READER_NOISE_RE = re.compile(
    r"(?:天天看的|看這個養你|求订阅|求訂閱|求追读|求追讀|月票|推薦票|推荐票|打賞|打赏|收藏|評論|评论|書友|书友)"
)

_CHAPTER_HEADING_RE = re.compile(r"^第[一二三四五六七八九十百千零\d]+章")
_TRAILING_CITATION_RE = re.compile(r"([！？。，；：…—])([」』”\"]?)\s*\d{1,4}(?=\s|$)")
_STORY_CHAR_CLASS = r"A-Za-z0-9\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af\u0e00-\u0e7f"
_SHORT_NON_STORY_LINE_RE = re.compile(rf"^[^\n{_STORY_CHAR_CLASS}]{{1,40}}$", re.MULTILINE)


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
