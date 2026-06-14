"""Helper functions for translation toolkit.

Used by translate_ch.py for context building.
"""
import re
from typing import Iterable


def clean_source(raw: str) -> str:
    """Strip line numbers, reader comments, duplicate title (same as pre_chapter)."""
    parts = raw.split('\n---\n')
    body = parts[0]
    lines = body.split('\n')
    out = []
    in_body = False
    for line in lines[1:]:  # skip H1
        stripped = line.strip()
        if not in_body:
            if stripped == '' or '全球降臨' in stripped:
                continue
            if re.match(r'^第[一二三四五六七八九十百千零\d]+章', stripped):
                continue
            in_body = True
        out.append(line)
    text = '\n'.join(out)
    # Remove line numbers after CJK punctuation
    text = re.sub(
        r'([！？。，；：…—]+)\s*(\d{1,3})(?=\s|$)',
        r'\1',
        text,
    )
    # Remove non-CJK-non-Thai single lines (meta comments)
    text = re.sub(
        r'^[^\n\u4e00-\u9fff\u0e00-\u0e7f]{1,40}$',
        '',
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_unknown_terms(source_text: str, known_sources: Iterable[str]) -> list[str]:
    """Extract CN terms from source that aren't in glossary.

    Filters:
    - Single chars (too generic)
    - Whitelisted zones (【】、《》、already-translated)
    - Already-known terms
    - Common UI/site text (首頁, 字體, 目錄, etc.)
    - Repetitive UI text that appears in novel source navigation
    """
    known = set(known_sources)

    # Common UI/site text to skip (chinese web novel site navigation)
    UI_NOISE = {
        '首頁', '科幻小說', '玄幻小說', '都市言情', '歷史軍事', '遊戲競技',
        '加入書籤', '小說報錯', '投票推薦', '字體', '上一章', '下一章', '目錄',
        '關燈', '開燈', '下載', '客戶端', '手機看書', '繁體', '簡體',
        '上一頁', '下一頁', '返回', '確定', '取消', '提交', '下載本章',
        '請先', '登錄', '註冊', '忘記密碼', '會員中心', '我的書架',
        '正在加載', '加載中', '請稍候', '暫無', '評論', '書友',
        '全球降臨', '帶著嫂嫂', '末世種田', '第', '章', '回', '節', '頁', '卷',
    }
    known |= UI_NOISE

    # Strip whitelisted zones
    cleaned = re.sub(r'【[^】]*】', '', source_text)
    cleaned = re.sub(r'《[^》]*》', '', cleaned)
    cleaned = re.sub(r'「[^」]*」', '', cleaned)

    # Extract 2+ char CN sequences
    cn_terms = re.findall(r'[\u4e00-\u9fff]{2,}', cleaned)
    seen = set()
    unknown = []
    for term in cn_terms:
        if term not in known and term not in seen:
            seen.add(term)
            unknown.append(term)
    return unknown
