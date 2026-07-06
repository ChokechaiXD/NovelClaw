import json

from tools import batch_report


def test_batch_report_flags_structure_drift(tmp_path):
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    (chapters / "0001.th.json").write_text(
        json.dumps(
            {
                "paragraphs": [{"type": "narration", "text": "x"}],
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
