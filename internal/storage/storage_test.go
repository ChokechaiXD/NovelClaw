package storage

import (
	"os"
	"path/filepath"
	"testing"

	"novelclaw/internal/model"
)

func TestStorageSaveAndGet(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "novelclaw-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tempDir)

	store := NewStore(tempDir)

	// Test 1: Save Novel
	novel := &model.Novel{
		Slug:            "test-novel",
		Title:           "测试小说",
		TranslatedTitle: "นิยายทดสอบ",
		Author:          "นักเขียนทดสอบ",
		SourceLang:      "cn",
		TargetLang:      "th",
	}

	if err := store.SaveNovel(novel); err != nil {
		t.Fatalf("SaveNovel failed: %v", err)
	}

	// Test 2: Get Novel
	loaded, err := store.GetNovel("test-novel")
	if err != nil {
		t.Fatalf("GetNovel failed: %v", err)
	}
	if loaded.Title != "测试小说" || loaded.TranslatedTitle != "นิยายทดสอบ" {
		t.Errorf("Loaded novel data mismatch: %+v", loaded)
	}

	// Test 3: Save and Get Chapter
	srcParas := []string{"段落1", "段落2"}
	thParas := []string{"ย่อหน้าที่ 1", "ย่อหน้าที่ 2"}

	if err := store.SaveChapter("test-novel", 1, "第1章", "ตอนที่ 1", srcParas, thParas); err != nil {
		t.Fatalf("SaveChapter failed: %v", err)
	}

	ch, err := store.GetChapter("test-novel", 1)
	if err != nil {
		t.Fatalf("GetChapter failed: %v", err)
	}
	if len(ch.SourceText) != 2 || len(ch.TranslatedText) != 2 {
		t.Errorf("Chapter paragraphs mismatch: %+v", ch)
	}

	// Test 4: Glossary
	glossary := &model.NovelGlossary{
		NovelSlug: "test-novel",
		Terms: []model.GlossaryItem{
			{Term: "主角", Target: "พระเอก", Category: "character"},
		},
	}
	if err := store.SaveGlossary(glossary); err != nil {
		t.Fatalf("SaveGlossary failed: %v", err)
	}

	loadedGlossary, err := store.GetGlossary("test-novel")
	if err != nil {
		t.Fatalf("GetGlossary failed: %v", err)
	}
	if len(loadedGlossary.Terms) != 1 || loadedGlossary.Terms[0].Target != "พระเอก" {
		t.Errorf("Glossary mismatch: %+v", loadedGlossary)
	}

	// Test 5: List Chapters
	chapters, err := store.ListChapters("test-novel")
	if err != nil {
		t.Fatalf("ListChapters failed: %v", err)
	}
	if len(chapters) != 1 || chapters[0].ChapterNo != 1 || !chapters[0].HasTranslated {
		t.Errorf("ListChapters mismatch: %+v", chapters)
	}
}

func TestStorageReadExistingFiles(t *testing.T) {
	// Verify that storage can read existing novel folder structure if present
	novelDir := filepath.Join("..", "..", "novels", "global-descent")
	if _, err := os.Stat(novelDir); os.IsNotExist(err) {
		t.Skip("novels/global-descent not present, skipping")
	}

	store := NewStore(filepath.Join("..", "..", "novels"))
	novel, err := store.GetNovel("global-descent")
	if err != nil {
		t.Fatalf("Failed to read global-descent: %v", err)
	}
	if novel.Slug != "global-descent" {
		t.Errorf("Expected slug global-descent, got %s", novel.Slug)
	}
}
