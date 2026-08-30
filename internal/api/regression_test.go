package api

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"novelclaw/internal/config"
	"novelclaw/internal/model"
	"novelclaw/internal/storage"
)

func TestPreviousChapterContextUsesActualPredecessor(t *testing.T) {
	dir := t.TempDir()
	store := storage.NewStore(dir)
	if err := store.SaveNovel(&model.Novel{Slug: "n", Title: "N"}); err != nil {
		t.Fatal(err)
	}
	if err := store.SaveChapter("n", 1, "one", "", []string{"old-1", "old-2", "old-3", "old-4"}, nil); err != nil {
		t.Fatal(err)
	}
	if err := store.SaveChapter("n", 2, "two", "", []string{"CURRENT-TEXT"}, nil); err != nil {
		t.Fatal(err)
	}
	chapters, _ := store.ListChapters("n")
	got := previousChapterContext(store, "n", 2, chapters)
	if strings.Contains(got, "CURRENT-TEXT") {
		t.Fatalf("context leaked current chapter: %q", got)
	}
	if !strings.Contains(got, "old-2\nold-3\nold-4") {
		t.Fatalf("wrong predecessor context: %q", got)
	}
}
func TestUpdateConfigClearsKeyWhenRouterChanges(t *testing.T) {
	dir := t.TempDir()
	cfg := &config.AppConfig{DataDir: dir, RouterURL: "https://old.example/v1", APIKey: "secret-key", ConfigPath: dir + "\\config.json"}
	store := storage.NewStore(dir)
	router, _ := SetupRouter(cfg, store)

	body := bytes.NewBufferString(`{"routerUrl":"https://new.example/v1"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/config", body)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	if got := cfg.ActiveProvider().APIKey; got != "" {
		t.Fatalf("API key carried to new router: %q", got)
	}
}

func TestTranslationWithNoSourceFinishesAsError(t *testing.T) {
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = dir
	cfg.ConfigPath = filepath.Join(dir, "config.json")
	store := storage.NewStore(dir)
	if err := store.SaveNovel(&model.Novel{Slug: "empty", Title: "Empty"}); err != nil {
		t.Fatal(err)
	}
	broker := NewSSEBroker()
	ch := subscribeBroker(broker)
	h := NewAPIHandler(cfg, store, broker)
	h.runTranslationJob(context.Background(), "job-empty", model.TranslateRequest{
		NovelSlug: "empty", StartChapter: 1, EndChapter: 1, Model: "unused",
	})
	events := drainEvents(t, ch)
	if len(events) == 0 {
		t.Fatal("expected translation events")
	}
	last := events[len(events)-1]
	if last["status"] != "error" {
		t.Fatalf("final status=%v event=%#v", last["status"], last)
	}
	if int(last["percentage"].(float64)) != 100 {
		t.Fatalf("final percentage=%v", last["percentage"])
	}
}
