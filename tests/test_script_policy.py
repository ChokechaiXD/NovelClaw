from qa.script_policy import detect_script_leaks


def test_script_leaks_report_paragraph_and_character_coordinates():
    paragraphs = [
        "ย่อหน้าแรกเป็นภาษาไทยทั้งหมด",
        "ย่อหน้าที่สองมี OpenBeta และ 漢 ปะปนอยู่",
    ]

    result = detect_script_leaks(paragraphs, target_lang="th")

    latin = next(leak for leak in result.leaks if leak.script == "Latin")
    han = next(leak for leak in result.leaks if leak.script == "Han")
    assert latin.paragraph_index == 1
    assert latin.char_offset == paragraphs[1].index("OpenBeta")
    assert han.paragraph_index == 1
    assert han.char_offset == paragraphs[1].index("漢")

