package storage

import (
	"testing"

	"novelclaw/internal/model"
)

func TestChapterCacheIsolationAndInvalidation(t *testing.T) {
	store := NewStore(t.TempDir())
	if err := store.SaveNovel(&model.Novel{Slug: "cache-test", Title: "Cache Test"}); err != nil {
		t.Fatal(err)
	}
	if err := store.SaveChapter("cache-test", 1, "One", "", []string{"src"}, nil); err != nil {
		t.Fatal(err)
	}

	first, err := store.ListChapters("cache-test")
	if err != nil || len(first) != 1 {
		t.Fatalf("first list: len=%d err=%v", len(first), err)
	}
	first[0].TitleSource = "caller mutation"

	cached, err := store.ListChapters("cache-test")
	if err != nil || cached[0].TitleSource == "caller mutation" {
		t.Fatalf("cached result leaked caller mutation: %#v err=%v", cached, err)
	}

	if err := store.SaveChapter("cache-test", 2, "Two", "", []string{"src2"}, nil); err != nil {
		t.Fatal(err)
	}
	afterWrite, err := store.ListChapters("cache-test")
	if err != nil {
		t.Fatal(err)
	}
	if len(afterWrite) != 2 || afterWrite[1].ChapterNo != 2 {
		t.Fatalf("cache was not invalidated after SaveChapter: %#v", afterWrite)
	}
}
