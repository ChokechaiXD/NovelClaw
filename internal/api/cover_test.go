package api

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"novelclaw/internal/config"
	"novelclaw/internal/model"
	"novelclaw/internal/storage"
)

func TestNovelCoverUpload(t *testing.T) {
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = filepath.Join(dir, "novels")
	store := storage.NewStore(cfg.DataDir)
	if err := store.SaveNovel(&model.Novel{Slug: "demo", Title: "Demo"}); err != nil {
		t.Fatal(err)
	}
	router, _ := SetupRouter(cfg, store)

	png := append([]byte{0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A}, bytes.Repeat([]byte{0}, 16)...)
	req := httptest.NewRequest(http.MethodPost, "/api/novels/demo/cover", bytes.NewReader(png))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusNoContent {
		t.Fatalf("upload status=%d body=%s", w.Code, w.Body.String())
	}
	if _, err := os.Stat(filepath.Join(cfg.DataDir, "demo", "cover.png")); err != nil {
		t.Fatalf("cover.png missing: %v", err)
	}

	get := httptest.NewRequest(http.MethodGet, "/api/novels/demo/cover", nil)
	gw := httptest.NewRecorder()
	router.ServeHTTP(gw, get)
	if gw.Code != http.StatusOK {
		t.Fatalf("get status=%d", gw.Code)
	}
	if got := gw.Header().Get("Content-Type"); got != "image/png" {
		t.Fatalf("content-type=%q", got)
	}
}

func TestNovelCoverUploadRejectsNonImage(t *testing.T) {
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = filepath.Join(dir, "novels")
	store := storage.NewStore(cfg.DataDir)
	if err := store.SaveNovel(&model.Novel{Slug: "demo", Title: "Demo"}); err != nil {
		t.Fatal(err)
	}
	router, _ := SetupRouter(cfg, store)

	req := httptest.NewRequest(http.MethodPost, "/api/novels/demo/cover", bytes.NewReader([]byte("definitely not an image file")))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusUnsupportedMediaType {
		t.Fatalf("status=%d", w.Code)
	}
	if _, err := os.Stat(filepath.Join(cfg.DataDir, "demo", "cover.png")); !os.IsNotExist(err) {
		t.Fatalf("junk must not be stored, err=%v", err)
	}
}

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
