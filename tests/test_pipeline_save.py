import json

import pipeline
import pipeline_save


def test_save_chapter_writes_canonical_json_and_marks_needs_review(tmp_path, monkeypatch):
    slug = "fixture-novel"
    out_path = tmp_path / slug / "0007.th.json"

    monkeypatch.setattr(pipeline_save, "chapter_dir", lambda _slug: tmp_path / _slug)
    monkeypatch.setattr(pipeline_save, "chapter_path", lambda _slug, _ch, _lang: out_path)

    result = pipeline_save.save_chapter(
        classified=[{"type": "narration", "text": "เฉาซิงเงยหน้าขึ้น"}],
        ch_num=7,
        slug=slug,
        source_text="第7章 归来",
        source_lang="cn",
        provider_name="mock-provider",
        model_name="mock-model",
        quality_record={"passed": False, "score": 74},
        source_profile={"paragraphCount": 1},
    )

    data = json.loads(out_path.read_text(encoding="utf-8"))

    assert result == out_path
    assert data["novelId"] == slug
    assert data["chapterNo"] == 7
    assert data["status"] == "needs_review"
    assert data["title"]["translated"] == "ตอนที่ 7 归来"
    assert data["paragraphs"] == [{"type": "narration", "text": "เฉาซิงเงยหน้าขึ้น"}]
    assert data["meta"] == {
        "provider": "mock-provider",
        "model": "mock-model",
        "promptProfile": "faithful_default",
        "sourceProfile": {"paragraphCount": 1},
    }
    assert data["qualityRecord"] == {"passed": False, "score": 74}
    assert pipeline.save_chapter is pipeline_save.save_chapter
    assert pipeline._get_title is pipeline_save.get_title
