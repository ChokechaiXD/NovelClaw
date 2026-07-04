from types import SimpleNamespace

import pipeline
import pipeline_glossary


class _FakePolicy:
    def apply_to_text(self, text):
        return SimpleNamespace(text=text.replace("HP", "พลังชีวิต"))


def test_apply_glossary_post_replaces_terms_and_keeps_end_marker(monkeypatch):
    monkeypatch.setattr("qa.term_policy.get_term_policy", lambda _lang: _FakePolicy())

    result = pipeline_glossary.apply_glossary_post(
        ["เฉาซิงมี HP เต็ม", "(จบบท)"],
        target_lang="th",
    )

    assert result == ["เฉาซิงมี พลังชีวิต เต็ม", "(จบบท)"]
    assert pipeline.apply_glossary_post is pipeline_glossary.apply_glossary_post
