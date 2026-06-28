from pipeline import clean_source


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

