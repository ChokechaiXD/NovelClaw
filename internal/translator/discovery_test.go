package translator

import (
	"testing"

	"novelclaw/internal/model"
)

func TestParseGlossaryJSON_PlainJSON(t *testing.T) {
	input := `[{"term":"曹星","target":"เฉาซิง","category":"character","notes":"ตัวเอก"}]`
	items := parseGlossaryJSON(input)

	if len(items) != 1 {
		t.Fatalf("Expected 1 item, got %d", len(items))
	}
	if items[0].Term != "曹星" {
		t.Errorf("Term = %q, want 曹星", items[0].Term)
	}
	if items[0].Target != "เฉาซิง" {
		t.Errorf("Target = %q, want เฉาซิง", items[0].Target)
	}
}

func TestParseGlossaryJSON_MarkdownCodeBlock(t *testing.T) {
	input := "```json\n[{\"term\":\"柳慕雪\",\"target\":\"หลิวมู่เสวี่ย\",\"category\":\"character\"}]\n```"
	items := parseGlossaryJSON(input)

	if len(items) != 1 {
		t.Fatalf("Expected 1 item from markdown block, got %d", len(items))
	}
	if items[0].Term != "柳慕雪" {
		t.Errorf("Term = %q, want 柳慕雪", items[0].Term)
	}
}

func TestParseGlossaryJSON_TextSurroundingJSON(t *testing.T) {
	input := `Here are the terms I found:
[{"term":"冰封纪元","target":"ยุคน้ำแข็ง","category":"custom"}]
That's all I found.`

	items := parseGlossaryJSON(input)
	if len(items) != 1 {
		t.Fatalf("Expected 1 item from embedded JSON, got %d", len(items))
	}
	if items[0].Term != "冰封纪元" {
		t.Errorf("Term = %q, want 冰封纪元", items[0].Term)
	}
}

func TestParseGlossaryJSON_MalformedJSON(t *testing.T) {
	inputs := []string{
		"this is not json",
		"{broken}",
		"",
		"   ",
	}
	for _, input := range inputs {
		items := parseGlossaryJSON(input)
		if items == nil {
			// nil is acceptable — just make sure it doesn't panic
			continue
		}
	}
}

func TestParseGlossaryJSON_MultipleItems(t *testing.T) {
	input := `[
		{"term":"曹星","target":"เฉาซิง","category":"character","notes":"ตัวเอก"},
		{"term":"柳慕雪","target":"หลิวมู่เสวี่ย","category":"character","notes":"พี่สะใภ้"},
		{"term":"冰封纪元","target":"ยุคน้ำแข็ง","category":"custom","notes":"ชื่อเกม"}
	]`
	items := parseGlossaryJSON(input)
	if len(items) != 3 {
		t.Errorf("Expected 3 items, got %d", len(items))
	}
}

func TestFilterRelevantGlossary_Basic(t *testing.T) {
	g := &model.NovelGlossary{
		NovelSlug: "test-novel",
		Terms: []model.GlossaryItem{
			{Term: "曹星", Target: "เฉาซิง", Category: "character"},
			{Term: "柳慕雪", Target: "หลิวมู่เสวี่ย", Category: "character"},
			{Term: "冰封纪元", Target: "ยุคน้ำแข็ง", Category: "custom"},
		},
	}
	paras := []string{"这里有曹星出场了", "另一段没有名字"}

	filtered := FilterRelevantGlossary(g, paras)
	if len(filtered.Terms) != 1 {
		t.Fatalf("Expected 1 relevant term, got %d", len(filtered.Terms))
	}
	if filtered.Terms[0].Term != "曹星" {
		t.Errorf("Filtered term = %q, want 曹星", filtered.Terms[0].Term)
	}
}

func TestFilterRelevantGlossary_NilGlossary(t *testing.T) {
	result := FilterRelevantGlossary(nil, []string{"hello"})
	if result != nil {
		t.Error("Expected nil for nil glossary input")
	}
}

func TestFilterRelevantGlossary_EmptyTerms(t *testing.T) {
	g := &model.NovelGlossary{Terms: []model.GlossaryItem{}}
	result := FilterRelevantGlossary(g, []string{"hello"})
	if len(result.Terms) != 0 {
		t.Error("Expected 0 terms for empty glossary")
	}
}

func TestFilterRelevantGlossary_AllMatch(t *testing.T) {
	g := &model.NovelGlossary{
		Terms: []model.GlossaryItem{
			{Term: "ABC", Target: "เอบีซี"},
			{Term: "DEF", Target: "ดีอีเอฟ"},
		},
	}
	paras := []string{"Text with ABC and DEF in it"}

	filtered := FilterRelevantGlossary(g, paras)
	if len(filtered.Terms) != 2 {
		t.Errorf("Expected 2 terms, got %d", len(filtered.Terms))
	}
}

func TestParseGlossaryJSONStrictRejectsMalformed(t *testing.T) {
	if _, err := parseGlossaryJSONStrict("not json at all"); err == nil {
		t.Fatal("expected malformed glossary output to return an error")
	}
	items, err := parseGlossaryJSONStrict("[]")
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 0 {
		t.Fatalf("expected empty valid array, got %v", items)
	}
}
