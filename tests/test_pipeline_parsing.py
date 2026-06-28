from pipeline import parse_output


def test_parse_output_strips_markdown_fences():
    output = """```text
เฉาซิงลืมตาขึ้นท่ามกลางเสียงโกลาหล

"รีบไปกันเถอะ" เขาพูดเสียงต่ำ
```"""

    paragraphs = parse_output(output, ch_num=1)

    assert paragraphs == [
        "เฉาซิงลืมตาขึ้นท่ามกลางเสียงโกลาหล",
        '"รีบไปกันเถอะ" เขาพูดเสียงต่ำ',
    ]


def test_parse_output_strips_unknown_language_fence():
    output = """```thai
เฉาซิงมองไปรอบห้อง
```"""

    paragraphs = parse_output(output, ch_num=1)

    assert paragraphs == ["เฉาซิงมองไปรอบห้อง"]
