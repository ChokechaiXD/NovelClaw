package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"novelclaw/internal/model"
	"novelclaw/internal/scraper"
	"novelclaw/internal/storage"
)

func postImport(t *testing.T, router http.Handler, payload map[string]interface{}) *httptest.ResponseRecorder {
	t.Helper()
	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/api/import", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	return w
}
func TestManualImportUsesNovelTitle(t *testing.T) {
	_, store, router, cleanup := setupTestEnv(t)
	defer cleanup()

	w := postImport(t, router, map[string]interface{}{
		"novelSlug":    "manual-novel",
		"novelTitle":   "ชื่อเรื่องจริง",
		"title":        "ตอนที่เจ็ด",
		"genre":        "fantasy",
		"startChapter": 7,
		"rawContent":   "ย่อหน้าแรก\n\nย่อหน้าที่สอง",
	})
	if w.Code != http.StatusOK {
		t.Fatalf("import status=%d body=%s", w.Code, w.Body.String())
	}
	novel, err := store.GetNovel("manual-novel")
	if err != nil {
		t.Fatal(err)
	}
	if novel.Title != "ชื่อเรื่องจริง" {
		t.Fatalf("novel title=%q", novel.Title)
	}
	chapter, err := store.GetChapter("manual-novel", 7)
	if err != nil {
		t.Fatal(err)
	}
	if chapter.SourceTitle != "ตอนที่เจ็ด" {
		t.Fatalf("chapter title=%q", chapter.SourceTitle)
	}
}
func TestManualImportRejectsWhitespaceWithoutCreatingNovel(t *testing.T) {
	_, store, router, cleanup := setupTestEnv(t)
	defer cleanup()

	w := postImport(t, router, map[string]interface{}{
		"novelSlug":  "empty-novel",
		"novelTitle": "ไม่ควรถูกสร้าง",
		"title":      "ตอนที่ 1",
		"rawContent": "   \n\t  ",
	})
	if w.Code != http.StatusBadRequest {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	_, err := store.GetNovel("empty-novel")
	if !errors.Is(err, storage.ErrNovelNotFound) {
		t.Fatalf("expected ErrNovelNotFound, got %v", err)
	}
}

func TestManualImportDoesNotOverwriteCorruptMetadata(t *testing.T) {
	_, store, router, cleanup := setupTestEnv(t)
	defer cleanup()

	dir := filepath.Join(store.DataDir, "bad-novel")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "novel.json")
	original := []byte(`{"title":`)
	if err := os.WriteFile(path, original, 0644); err != nil {
		t.Fatal(err)
	}
	w := postImport(t, router, map[string]interface{}{
		"novelSlug":  "bad-novel",
		"novelTitle": "ห้ามเขียนทับ",
		"title":      "ตอนที่ 1",
		"rawContent": "เนื้อหาทดสอบ",
	})
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	after, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(after, original) {
		t.Fatalf("corrupt metadata was overwritten: %q", string(after))
	}
}

func TestNormalizeImportRange(t *testing.T) {
	tests := []struct {
		start, end, available         int
		wantStart, wantEnd, wantTotal int
		wantErr                       bool
	}{
		{0, 0, 10, 1, 10, 10, false},
		{5, 8, 10, 5, 8, 4, false},
		{9, 99, 10, 9, 10, 2, false},
		{11, 0, 10, 0, 0, 0, true},
		{8, 7, 10, 0, 0, 0, true},
	}
	for _, tc := range tests {
		start, end, total, err := normalizeImportRange(tc.start, tc.end, tc.available)
		if tc.wantErr {
			if err == nil {
				t.Fatalf("normalizeImportRange(%d,%d,%d) expected error", tc.start, tc.end, tc.available)
			}
			continue
		}
		if err != nil {
			t.Fatalf("normalizeImportRange(%d,%d,%d): %v", tc.start, tc.end, tc.available, err)
		}
		if start != tc.wantStart || end != tc.wantEnd || total != tc.wantTotal {
			t.Fatalf("got (%d,%d,%d), want (%d,%d,%d)", start, end, total, tc.wantStart, tc.wantEnd, tc.wantTotal)
		}
	}
}

func TestImportPercentage(t *testing.T) {
	tests := map[[2]int]int{
		{0, 4}: 0,
		{1, 4}: 25,
		{3, 4}: 75,
		{4, 4}: 100,
		{5, 4}: 100,
		{1, 0}: 0,
	}
	for input, want := range tests {
		if got := importPercentage(input[0], input[1]); got != want {
			t.Fatalf("importPercentage(%d,%d)=%d want %d", input[0], input[1], got, want)
		}
	}
}

type fakeNovelSource struct {
	toc        *scraper.ScrapedNovelInfo
	tocErr     error
	chapters   map[string]*scraper.ScrapedChapter
	chapterErr map[string]error
}

func (f *fakeNovelSource) FetchChapterContext(_ context.Context, url string) (*scraper.ScrapedChapter, error) {
	if err := f.chapterErr[url]; err != nil {
		return nil, err
	}
	if chapter := f.chapters[url]; chapter != nil {
		return chapter, nil
	}
	return nil, fmt.Errorf("chapter not found: %s", url)
}

func (f *fakeNovelSource) FetchTOCContext(_ context.Context, _ string) (*scraper.ScrapedNovelInfo, error) {
	if f.tocErr != nil {
		return nil, f.tocErr
	}
	return f.toc, nil
}

func subscribeBroker(b *SSEBroker) chan []byte {
	ch := make(chan []byte, 32)
	b.mu.Lock()
	b.clients[ch] = true
	b.mu.Unlock()
	return ch
}

func drainEvents(t *testing.T, ch chan []byte) []map[string]interface{} {
	t.Helper()
	var events []map[string]interface{}
	for {
		select {
		case raw := <-ch:
			var event map[string]interface{}
			if err := json.Unmarshal(raw, &event); err != nil {
				t.Fatal(err)
			}
			events = append(events, event)
		default:
			return events
		}
	}
}

func TestURLImportPartialUsesRelativeProgress(t *testing.T) {
	dir := t.TempDir()
	store := storage.NewStore(dir)
	broker := NewSSEBroker()
	ch := subscribeBroker(broker)
	source := &fakeNovelSource{
		toc: &scraper.ScrapedNovelInfo{
			Title: "Import Book",
			Chapters: []scraper.ScrapedChapter{
				{ChapterNo: 1, Title: "One", URL: "c1"},
				{ChapterNo: 2, Title: "Two", URL: "c2"},
				{ChapterNo: 3, Title: "Three", URL: "c3"},
			},
		},
		chapters: map[string]*scraper.ScrapedChapter{
			"c2": {ChapterNo: 2, Title: "Two", Paragraphs: []string{"ok"}},
		},
		chapterErr: map[string]error{
			"root": fmt.Errorf("not a chapter"),
			"c3":   fmt.Errorf("network failure"),
		},
	}
	h := &APIHandler{store: store, scraper: source, sse: broker, importDelay: 0}
	h.runImportJob(context.Background(), "import_test", model.ImportRequest{
		URL: "root", NovelSlug: "partial-book", StartChapter: 2, EndChapter: 3,
	})

	events := drainEvents(t, ch)
	if len(events) != 3 {
		t.Fatalf("events=%d want 3: %#v", len(events), events)
	}
	if events[0]["type"] != "import_progress" || int(events[0]["current"].(float64)) != 1 || int(events[0]["total"].(float64)) != 2 {
		t.Fatalf("first progress=%#v", events[0])
	}
	if int(events[0]["percentage"].(float64)) != 50 {
		t.Fatalf("first percentage=%v", events[0]["percentage"])
	}
	last := events[len(events)-1]
	if last["type"] != "import_partial" {
		t.Fatalf("final event=%#v", last)
	}
	if int(last["imported"].(float64)) != 1 || int(last["failed"].(float64)) != 1 || int(last["total"].(float64)) != 2 {
		t.Fatalf("partial counts=%#v", last)
	}
	if _, err := store.GetChapter("partial-book", 2); err != nil {
		t.Fatalf("successful chapter not saved: %v", err)
	}
	if _, err := store.GetChapter("partial-book", 3); err == nil {
		t.Fatal("failed chapter should not exist")
	}
}

func TestGetNovelReturns500ForCorruptMetadata(t *testing.T) {
	_, store, router, cleanup := setupTestEnv(t)
	defer cleanup()

	dir := filepath.Join(store.DataDir, "corrupt-get")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "novel.json"), []byte(`{"title":`), 0644); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodGet, "/api/novels/corrupt-get", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
}

type blockingNovelSource struct {
	started chan struct{}
}

func (b *blockingNovelSource) FetchTOCContext(ctx context.Context, _ string) (*scraper.ScrapedNovelInfo, error) {
	select {
	case <-b.started:
	default:
		close(b.started)
	}
	<-ctx.Done()
	return nil, ctx.Err()
}

func (b *blockingNovelSource) FetchChapterContext(ctx context.Context, _ string) (*scraper.ScrapedChapter, error) {
	<-ctx.Done()
	return nil, ctx.Err()
}

func TestURLImportCancellationStopsActiveFetch(t *testing.T) {
	dir := t.TempDir()
	store := storage.NewStore(dir)
	broker := NewSSEBroker()
	events := subscribeBroker(broker)
	source := &blockingNovelSource{started: make(chan struct{})}
	h := &APIHandler{store: store, scraper: source, sse: broker, importDelay: 0}

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		defer close(done)
		h.runImportJob(ctx, "cancel_fetch", model.ImportRequest{URL: "slow", NovelSlug: "cancel-book"})
	}()

	select {
	case <-source.started:
	case <-time.After(time.Second):
		t.Fatal("fetch never started")
	}
	cancel()
	select {
	case <-done:
	case <-time.After(300 * time.Millisecond):
		t.Fatal("import worker did not stop promptly after cancellation")
	}

	got := drainEvents(t, events)
	if len(got) != 1 || got[0]["type"] != "import_cancelled" {
		t.Fatalf("events=%#v", got)
	}
	if int(got[0]["current"].(float64)) != 0 || int(got[0]["failed"].(float64)) != 0 {
		t.Fatalf("cancel event should not count an interrupted fetch as failure: %#v", got[0])
	}
	if _, err := store.GetNovel("cancel-book"); !errors.Is(err, storage.ErrNovelNotFound) {
		t.Fatalf("cancelled fetch unexpectedly created metadata: %v", err)
	}
}
