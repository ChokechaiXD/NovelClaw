package scraper

import "testing"

func TestQidianURLParsing(t *testing.T) {
	s := NewQidianScraper()
	cases := []string{
		"https://www.qidian.com/book/1040133596/",
		"https://m.qidian.com/book/1040133596/catalog/",
		"https://m.qidian.com/chapter/1040133596/791715198/",
	}
	for _, raw := range cases {
		if !s.CanHandle(raw) {
			t.Fatalf("expected Qidian URL to be handled: %s", raw)
		}
		id, err := qidianBookID(raw)
		if err != nil || id != "1040133596" {
			t.Fatalf("qidianBookID(%q)=%q,%v", raw, id, err)
		}
	}
	if s.CanHandle("https://example.com/book/1040133596/") {
		t.Fatal("non-Qidian URL must not be handled")
	}
}

func TestQidianChapterIDs(t *testing.T) {
	bookID, chapterID, err := qidianChapterIDs("https://www.qidian.com/chapter/1040133596/791715198/")
	if err != nil {
		t.Fatal(err)
	}
	if bookID != "1040133596" || chapterID != "791715198" {
		t.Fatalf("unexpected IDs: %s %s", bookID, chapterID)
	}
}

func TestQidianParagraphs(t *testing.T) {
	got := qidianParagraphs("<p>第一段<p>第二段<p>第三段")
	if len(got) != 3 {
		t.Fatalf("paragraph count=%d, want 3: %#v", len(got), got)
	}
	if got[0] != "第一段" || got[2] != "第三段" {
		t.Fatalf("unexpected paragraphs: %#v", got)
	}
}
