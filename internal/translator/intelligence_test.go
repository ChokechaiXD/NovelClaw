package translator

import (
	"strings"
	"testing"

	"novelclaw/internal/model"
)

func TestEvaluateTranslationQualityPerfect(t *testing.T) {
	report := EvaluateTranslationQuality(
		"novel", 1,
		[]string{"第一段", "第二段"},
		[]string{"ย่อหน้าแรก", "ย่อหน้าที่สอง"},
		nil,
	)
	if report.Score != 100 || len(report.Issues) != 0 {
		t.Fatalf("unexpected report: %+v", report)
	}
}

func TestEvaluateTranslationQualityFindsStructuralIssues(t *testing.T) {
	g := &model.NovelGlossary{Terms: []model.GlossaryItem{{Term: "曹星", Target: "เฉาซิง"}}}
	report := EvaluateTranslationQuality(
		"novel", 2,
		[]string{"曹星有100金币", "第二段"},
		[]string{"ตัวเอกมี 90 เหรียญ"},
		g,
	)
	if report.Score >= 100 || len(report.Issues) < 2 {
		t.Fatalf("expected QA issues, got %+v", report)
	}
}

func TestBuildMemoryContextUsesCuratedAndGlossaryCharacters(t *testing.T) {
	memory := &model.NovelMemory{
		StorySummary: "เรื่องราวหลัก",
		Characters: []model.CharacterMemory{{
			SourceName: "曹星", ThaiName: "เฉาซิง", Role: "ตัวเอก", Pronouns: "เขา",
		}},
		Facts: []string{"ข้อเท็จจริงสำคัญ"},
	}
	glossary := &model.NovelGlossary{Terms: []model.GlossaryItem{
		{Term: "曹星", Target: "เฉาซิง", Category: "character"},
		{Term: "柳慕雪", Target: "หลิวมู่เสวี่ย", Category: "character"},
	}}
	ctx := BuildMemoryContext(memory, glossary)
	for _, want := range []string{"เรื่องราวหลัก", "เฉาซิง", "หลิวมู่เสวี่ย", "ข้อเท็จจริงสำคัญ"} {
		if !strings.Contains(ctx, want) {
			t.Fatalf("memory context missing %q: %s", want, ctx)
		}
	}
	if strings.Count(ctx, "เฉาซิง") != 1 {
		t.Fatalf("curated character duplicated by glossary: %s", ctx)
	}
}

func TestParseNovelMemoryCandidateFromFencedJSON(t *testing.T) {
	raw := "```json\n{\"storySummary\":\"summary\",\"characters\":[{\"sourceName\":\"A\",\"thaiName\":\"เอ\"}],\"facts\":[\"fact\"]}\n```"
	memory, err := ParseNovelMemoryCandidate(raw)
	if err != nil {
		t.Fatal(err)
	}
	if memory.StorySummary != "summary" || len(memory.Characters) != 1 || len(memory.Facts) != 1 {
		t.Fatalf("unexpected memory: %+v", memory)
	}
}

func TestMergeNovelMemoryPreservesCuratedFields(t *testing.T) {
	existing := &model.NovelMemory{Characters: []model.CharacterMemory{{
		SourceName: "A", ThaiName: "เอ", Role: "curated-role", Pronouns: "curated-pronoun", Notes: "curated-note",
	}}, Facts: []string{"existing"}}
	candidate := &model.NovelMemory{StorySummary: "fresh", Characters: []model.CharacterMemory{{
		SourceName: "A", ThaiName: "เอใหม่", Role: "ai-role", Gender: "male", Pronouns: "ai-pronoun", Notes: "ai-note",
	}}, Facts: []string{"existing", "new"}}
	merged := MergeNovelMemory(existing, candidate, false)
	if merged.StorySummary != "fresh" || len(merged.Facts) != 2 || len(merged.Characters) != 1 {
		t.Fatalf("unexpected merged memory: %+v", merged)
	}
	ch := merged.Characters[0]
	if ch.Role != "curated-role" || ch.Pronouns != "curated-pronoun" || ch.Notes != "curated-note" {
		t.Fatalf("curated fields overwritten: %+v", ch)
	}
	if ch.Gender != "male" {
		t.Fatalf("blank curated field was not filled: %+v", ch)
	}
}

// A candidate built from chapters translated AFTER the stored memory must
// refresh stale descriptive fields (levels, roles, locations change over a
// long novel) while identity fields stay anchored.
func TestMergeNovelMemoryFreshRefreshesStaleFields(t *testing.T) {
	existing := &model.NovelMemory{Characters: []model.CharacterMemory{{
		SourceName: "曹星", ThaiName: "เฉาซิง", Role: "ผู้คุ้มค่าย", Pronouns: "เขา",
		Notes: "ลอร์ดเลเวล 17 ปราการเมฆน้ำแข็ง",
	}}}
	candidate := &model.NovelMemory{Characters: []model.CharacterMemory{{
		SourceName: "曹星", ThaiName: "เฉาซิง(ใหม่)", Role: "ลอร์ดมือปราบ", Pronouns: "เขา",
		Notes: "ลอร์ดเลเวล 42 อาณาเขตเหนือทะเลทราย",
	}}}
	merged := MergeNovelMemory(existing, candidate, true)
	ch := merged.Characters[0]
	if ch.Role != "ลอร์ดมือปราบ" || ch.Notes != "ลอร์ดเลเวล 42 อาณาเขตเหนือทะเลทราย" {
		t.Fatalf("stale fields were not refreshed: %+v", ch)
	}
	if ch.ThaiName != "เฉาซิง" {
		t.Fatalf("identity rename must stay a human decision: %+v", ch)
	}
}

func TestParseQARepairCandidateRequiresExactParagraphCount(t *testing.T) {
	_, _, err := ParseQARepairCandidate(`{"title":"t","paragraphs":["one"]}`, 2)
	if err == nil {
		t.Fatal("expected paragraph count error")
	}
	title, paragraphs, err := ParseQARepairCandidate(`{"title":"t","paragraphs":["one","two"]}`, 2)
	if err != nil || title != "t" || len(paragraphs) != 2 {
		t.Fatalf("unexpected candidate title=%q paragraphs=%v err=%v", title, paragraphs, err)
	}
}
