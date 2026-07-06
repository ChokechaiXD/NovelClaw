import json

from tools import batch_report


def test_batch_report_flags_structure_drift(tmp_path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "0001.th.json").write_text(
        json.dumps(
            {
                "paragraphs": (
                    [{"type": "dialogue", "text": '"x"'} for _ in range(5)]
                    + [{"type": "system", "text": "【x】"} for _ in range(7)]
                    + [{"type": "narration", "text": "x"} for _ in range(48)]
                ),
                "meta": {"model": "m"},
                "qualityRecord": {
                    "score": 100,
                    "passed": True,
                    "lengthRatio": 1.2,
                    "scriptLeaks": 0,
                    "structure": {
                        "source": {"paragraphCount": 100, "dialogueCount": 20, "systemMarkerCount": 10},
                        "output": {"paragraphCount": 60, "dialogueCount": 5, "systemMarkerCount": 7},
                    },
                    "attempts": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    source_paragraphs = (["「x」" for _ in range(20)] + ["【x】" for _ in range(10)] + ["plain source" for _ in range(70)])
    (chapters / "0001.cn.json").write_text(json.dumps({"paragraphs": source_paragraphs}), encoding="utf-8")

    row = batch_report.load_row(chapters, 1)

    assert row["status"] == "review"
    assert row["paragraphRatio"] == 0.6
    assert row["dialogueRatio"] == 0.25
    assert row["systemRatio"] == 0.7
    assert row["flags"] == ["paragraph_drift", "dialogue_drift", "system_drift"]


def test_batch_report_missing_row_has_stable_shape(tmp_path):
    row = batch_report.load_row(tmp_path, 2)

    assert row["status"] == "missing"
    assert row["score"] == ""
    assert row["flags"] == ["missing"]



def test_batch_report_flags_bad_canonical_name(tmp_path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "0208.cn.json").write_text(
        json.dumps({"paragraphs": ["曹星嘴角抽了抽。"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (chapters / "0208.th.json").write_text(
        json.dumps(
            {
                "paragraphs": [{"type": "narration", "text": "มุมปากของอู๋เจียฮุยก็กระตุก"}],
                "meta": {"model": "m"},
                "qualityRecord": {"score": 100, "passed": True, "lengthRatio": 1.0, "structure": {}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = batch_report.load_row(chapters, 208)

    assert "name_missing:曹星->เฉาซิง" in row["flags"]
    assert "name_bad:曹星->อู๋เจียฮุย" in row["flags"]



def test_batch_report_uses_adjusted_structure_counts(tmp_path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "0002.cn.json").write_text(
        json.dumps({"paragraphs": ["第2章", "投票推薦 加入書籤", "曹星說：「好。」", "【系統】"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (chapters / "0002.th.json").write_text(
        json.dumps(
            {
                "paragraphs": [
                    {"type": "narration", "text": "ตอนที่ 2"},
                    {"type": "dialogue", "text": 'เฉาซิงพูดว่า "ได้"'},
                    {"type": "system", "text": "【ระบบ】"},
                    {"type": "narration", "text": "จบตอน"},
                ],
                "meta": {"model": "m"},
                "qualityRecord": {
                    "score": 100,
                    "passed": True,
                    "lengthRatio": 1.0,
                    "structure": {
                        "source": {"paragraphCount": 99, "dialogueCount": 99, "systemMarkerCount": 99},
                        "output": {"paragraphCount": 1, "dialogueCount": 1, "systemMarkerCount": 1},
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = batch_report.load_row(chapters, 2)

    assert row["paragraphRatio"] == 1.0
    assert row["dialogueRatio"] == 1.0
    assert row["systemRatio"] == 1.0
    assert "paragraph_drift" not in row["flags"]
