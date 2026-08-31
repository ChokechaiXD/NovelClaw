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
		{Term: "曹星", Target: "ชื่อซ้ำควรถูกข้าม"},            // existing term → skipped
		{Term: "能量塔", Target: "หอพลังงาน", Category: "item"}, // genuinely new (not builtin)
		{Term: "", Target: "ไม่มีต้นฉบับ"},                   // invalid → skipped
		{Term: "冰封纪元", Target: "ค่ากากทับ builtin"},          // builtin-covered → skipped (sanitizer enforces locked value)
	}

	added, err := h.mergeDiscoveredGlossary("test-novel", discovered)
	if err != nil {
		t.Fatalf("mergeDiscoveredGlossary: %v", err)
	}
	if added != 1 {
		t.Fatalf("added = %d, want 1", added)
	}

	glossary, err := store.GetGlossary("test-novel")
	if err != nil {
		t.Fatalf("reload glossary: %v", err)
	}
	if len(glossary.Terms) != 2 {
		t.Fatalf("terms = %d, want 2", len(glossary.Terms))
	}
	for _, term := range glossary.Terms {
		if term.Term == "曹星" && term.Target != "เฉาซิง" {
			t.Fatalf("existing curated term was overwritten: %+v", term)
		}
		if term.Term == "冰封纪元" {
			t.Fatalf("builtin-covered term must not be re-added: %+v", term)
		}
	}
}
