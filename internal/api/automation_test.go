package api

import (
	"testing"

	"novelclaw/internal/model"
	"novelclaw/internal/storage"
)

// Auto-discovery must never overwrite curated glossary entries: existing
// terms win, only genuinely new terms are appended.
func TestMergeDiscoveredGlossary(t *testing.T) {
	store := storage.NewStore(t.TempDir())
	h := &APIHandler{store: store}

	if err := store.SaveGlossary(&model.NovelGlossary{
		NovelSlug: "test-novel",
		Terms:     []model.GlossaryItem{{Term: "曹星", Target: "เฉาซิง", Category: "character"}},
	}); err != nil {
		t.Fatalf("seed glossary: %v", err)
	}

	discovered := []model.GlossaryItem{
		{Term: "曹星", Target: "ชื่อซ้ำควรถูกข้าม"}, // existing term → skipped
		{Term: "柳慕雪", Target: "หลิวมู่เสวี่ย", Category: "character"},
		{Term: "", Target: "ไม่มีต้นฉบับ"}, // invalid → skipped
		{Term: "冰封纪元", Target: "ยุคน้ำแข็ง", Category: "custom"},
	}

	added, err := h.mergeDiscoveredGlossary("test-novel", discovered)
	if err != nil {
		t.Fatalf("mergeDiscoveredGlossary: %v", err)
	}
	if added != 2 {
		t.Fatalf("added = %d, want 2", added)
	}

	glossary, err := store.GetGlossary("test-novel")
	if err != nil {
		t.Fatalf("reload glossary: %v", err)
	}
	if len(glossary.Terms) != 3 {
		t.Fatalf("terms = %d, want 3", len(glossary.Terms))
	}
	for _, term := range glossary.Terms {
		if term.Term == "曹星" && term.Target != "เฉาซิง" {
			t.Fatalf("existing curated term was overwritten: %+v", term)
		}
	}
}
