package storage

import (
	"fmt"
	"sync"
	"testing"

	"novelclaw/internal/model"
)

func TestGlossaryCacheRefreshesAfterSave(t *testing.T) {
	store := NewStore(t.TempDir())
	glossary := &model.NovelGlossary{
		NovelSlug: "cache",
		Terms:     []model.GlossaryItem{{Term: "曹星", Target: "เฉาซิง"}},
	}
	if err := store.SaveGlossary(glossary); err != nil {
		t.Fatal(err)
	}
	if got := store.glossaryMap("cache")["曹星"]; got != "เฉาซิง" {
		t.Fatalf("cached target=%q", got)
	}

	glossary.Terms[0].Target = "เฉา ซิง"
	if err := store.SaveGlossary(glossary); err != nil {
		t.Fatal(err)
	}
	if got := store.glossaryMap("cache")["曹星"]; got != "เฉา ซิง" {
		t.Fatalf("cache did not refresh: %q", got)
	}
}

func TestConcurrentChapterWritesRemainComplete(t *testing.T) {
	store := NewStore(t.TempDir())
	if err := store.SaveNovel(&model.Novel{Slug: "parallel", Title: "Parallel"}); err != nil {
		t.Fatal(err)
	}

	const chapters = 64
	var wg sync.WaitGroup
	errs := make(chan error, chapters)
	for chapterNo := 1; chapterNo <= chapters; chapterNo++ {
		chapterNo := chapterNo
		wg.Add(1)
		go func() {
			defer wg.Done()
			title := fmt.Sprintf("Chapter %d", chapterNo)
			if err := store.SaveChapter("parallel", chapterNo, title, "", []string{"source"}, nil); err != nil {
				errs <- err
			}
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		t.Fatal(err)
	}

	list, err := store.ListChapters("parallel")
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != chapters {
		t.Fatalf("chapters=%d want=%d", len(list), chapters)
	}
	for i, chapter := range list {
		want := i + 1
		if chapter.ChapterNo != want || !chapter.HasSource {
			t.Fatalf("chapter[%d]=%#v", i, chapter)
		}
	}
}

func TestQualityReportCacheIsIncrementalAndIsolated(t *testing.T) {
	store := NewStore(t.TempDir())
	first := model.TranslationQualityReport{
		NovelSlug: "qa-cache", ChapterNo: 1, Score: 91,
		Issues: []model.TranslationQualityIssue{{Code: "x", Severity: "warning", Message: "one"}},
	}
	if err := store.SaveQualityReport(first); err != nil {
		t.Fatal(err)
	}
	warm, err := store.ListQualityReports("qa-cache")
	if err != nil || len(warm) != 1 {
		t.Fatalf("warm len=%d err=%v", len(warm), err)
	}
	warm[0].Score = 1
	warm[0].Issues[0].Message = "mutated"
	if err := store.SaveQualityReport(model.TranslationQualityReport{NovelSlug: "qa-cache", ChapterNo: 2, Score: 88}); err != nil {
		t.Fatal(err)
	}
	cached, err := store.ListQualityReports("qa-cache")
	if err != nil || len(cached) != 2 {
		t.Fatalf("cached len=%d err=%v", len(cached), err)
	}
	if cached[0].Score != 91 || cached[0].Issues[0].Message != "one" || cached[1].ChapterNo != 2 {
		t.Fatalf("cache corruption: %#v", cached)
	}
}
