package api

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"novelclaw/internal/config"
	"novelclaw/internal/storage"
)

func TestNovelCoverEndpoint(t *testing.T) {
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = filepath.Join(dir, "novels")
	novelDir := filepath.Join(cfg.DataDir, "demo")
	if err := os.MkdirAll(novelDir, 0o755); err != nil {
		t.Fatal(err)
	}
	want := []byte("webp-test-bytes")
	if err := os.WriteFile(filepath.Join(novelDir, "cover.webp"), want, 0o644); err != nil {
		t.Fatal(err)
	}
	router, _ := SetupRouter(cfg, storage.NewStore(cfg.DataDir))
	req := httptest.NewRequest(http.MethodGet, "/api/novels/demo/cover", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	if got := w.Header().Get("Content-Type"); got != "image/webp" {
		t.Fatalf("content-type=%q", got)
	}
	if got := w.Header().Get("X-Content-Type-Options"); got != "nosniff" {
		t.Fatalf("nosniff=%q", got)
	}
	if !bytes.Equal(w.Body.Bytes(), want) {
		t.Fatalf("body=%q", w.Body.Bytes())
	}
}

func TestNovelCoverEndpointMissing(t *testing.T) {
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = filepath.Join(dir, "novels")
	router, _ := SetupRouter(cfg, storage.NewStore(cfg.DataDir))
	req := httptest.NewRequest(http.MethodGet, "/api/novels/missing/cover", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNoContent {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
}
