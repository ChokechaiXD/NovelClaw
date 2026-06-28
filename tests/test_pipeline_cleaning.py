from pipeline import clean_source
from source_cleaner import find_source_noise


def test_clean_source_removes_trailing_citation_digits_after_quotes():
    raw = "\n".join(
        [
            "# chapter",
            "“阿星，大哥死了！”11",
            "“據說是因為拖欠工程款！”41",
            "玩家獲得了100點經驗值。",
        ]
    )

    cleaned = clean_source(raw)

    assert "！”11" not in cleaned
    assert "！”41" not in cleaned
    assert "“阿星，大哥死了！”" in cleaned
    assert "“據說是因為拖欠工程款！”" in cleaned
    assert "100點經驗值" in cleaned


def test_clean_source_preserves_first_story_line_without_header():
    raw = "\n".join(
        [
            "阿星睜開眼時，城市已經變成廢墟。",
            "玩家獲得了100點經驗值。",
        ]
    )

    cleaned = clean_source(raw)

    assert cleaned.startswith("阿星睜開眼時")
    assert "100點經驗值" in cleaned


def test_clean_source_removes_reader_noise_lines():
    raw = "\n".join(
        [
            "# chapter",
            "阿星推開門，霧氣湧入走廊。",
            "我丟，我天天看的，現在好了，看這個養你！",
            "“快走！”他低聲說。",
        ]
    )

    cleaned = clean_source(raw)

    assert "天天看的" not in cleaned
    assert "看這個養你" not in cleaned
    assert "阿星推開門" in cleaned
    assert "“快走！”" in cleaned
    assert find_source_noise(cleaned) == []


def test_find_source_noise_reports_unclean_artifacts():
    issues = find_source_noise("“阿星，大哥死了！”11\n我丟，我天天看的，現在好了，看這個養你！")

    kinds = {issue["kind"] for issue in issues}
    assert "trailing_citation" in kinds
    assert "reader_noise" in kinds
