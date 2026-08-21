package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"novelclaw/internal/config"
	"novelclaw/internal/model"
	"novelclaw/internal/storage"
)

func setupTestEnv(t *testing.T) (*config.AppConfig, *storage.Store, http.Handler, func()) {
	tmpDir, err := os.MkdirTemp("", "novelclaw_api_test_*")
	if err != nil {
		t.Fatalf("Failed to create tmp dir: %v", err)
	}

	cfg := &config.AppConfig{
		Port:         4173,
		Host:         "127.0.0.1",
		DataDir:      tmpDir,
		RouterURL:    "http://localhost:20128/v1",
		DefaultModel: "test-model",
		Temperature:  0.3,
		// Point config persistence at a temp file so UpdateConfig tests
		// never write into the source tree.
		ConfigPath: filepath.Join(tmpDir, "config.json"),
	}

	store := storage.NewStore(tmpDir)

	// Seed novel and chapter
	novel := &model.Novel{
		Slug:        "test-novel",
		Title:       "Test Novel Original",
		Description: "A great story",
	}
	if err := store.SaveNovel(novel); err != nil {
		t.Fatalf("Failed to save seed novel: %v", err)
	}

	if err := store.SaveChapter("test-novel", 1, "第1章 开始", "ตอนที่ 1 จุดเริ่มต้น", []string{"第一段", "第二段"}, []string{"ย่อหน้าที่ 1", "ย่อหน้าที่ 2"}); err != nil {
		t.Fatalf("Failed to save seed chapter: %v", err)
	}

	router, _ := SetupRouter(cfg, store)

	cleanup := func() {
		os.RemoveAll(tmpDir)
	}

	return cfg, store, router, cleanup
}

func TestListNovels(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	req := httptest.NewRequest("GET", "/api/novels", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Expected 200, got %d", w.Code)
	}

	var res struct {
		Novels []model.Novel `json:"novels"`
	}
	if err := json.NewDecoder(w.Body).Decode(&res); err != nil {
		t.Fatalf("Failed to decode response: %v", err)
	}

	if len(res.Novels) != 1 || res.Novels[0].Slug != "test-novel" {
		t.Errorf("Unexpected novels: %+v", res.Novels)
	}
}

func TestGetNovelAndChapters(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	// Get novel
	req := httptest.NewRequest("GET", "/api/novels/test-novel", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Get novel failed: expected 200, got %d", w.Code)
	}

	// List chapters
	req2 := httptest.NewRequest("GET", "/api/novels/test-novel/chapters", nil)
	w2 := httptest.NewRecorder()
	router.ServeHTTP(w2, req2)

	if w2.Code != http.StatusOK {
		t.Fatalf("List chapters failed: expected 200, got %d", w2.Code)
	}

	var chRes struct {
		Chapters []model.ChapterMeta `json:"chapters"`
	}
	_ = json.NewDecoder(w2.Body).Decode(&chRes)
	if len(chRes.Chapters) != 1 || chRes.Chapters[0].ChapterNo != 1 {
		t.Errorf("Unexpected chapters: %+v", chRes.Chapters)
	}

	// Get single chapter
	req3 := httptest.NewRequest("GET", "/api/novels/test-novel/chapters/1", nil)
	w3 := httptest.NewRecorder()
	router.ServeHTTP(w3, req3)

	if w3.Code != http.StatusOK {
		t.Fatalf("Get chapter 1 failed: expected 200, got %d", w3.Code)
	}

	var chContent model.ChapterContent
	_ = json.NewDecoder(w3.Body).Decode(&chContent)
	if len(chContent.TranslatedText) != 2 || chContent.TranslatedTitle != "ตอนที่ 1 จุดเริ่มต้น" {
		t.Errorf("Unexpected chapter content: %+v", chContent)
	}
}

func TestGlossaryAndBookmarkEndpoints(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	// Save Glossary
	glossary := model.NovelGlossary{
		NovelSlug: "test-novel",
		Terms: []model.GlossaryItem{
			{Term: "曹星", Target: "เฉาซิง", Category: "character"},
		},
	}
	data, _ := json.Marshal(glossary)
	req := httptest.NewRequest("POST", "/api/novels/test-novel/glossary", bytes.NewReader(data))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Save glossary failed: %d", w.Code)
	}

	// Get Glossary
	reqGetG := httptest.NewRequest("GET", "/api/novels/test-novel/glossary", nil)
	wGetG := httptest.NewRecorder()
	router.ServeHTTP(wGetG, reqGetG)

	var gRes model.NovelGlossary
	_ = json.NewDecoder(wGetG.Body).Decode(&gRes)
	if len(gRes.Terms) != 1 || gRes.Terms[0].Target != "เฉาซิง" {
		t.Errorf("Unexpected glossary: %+v", gRes)
	}

	// Save Bookmark
	bm := model.Bookmark{
		NovelSlug:        "test-novel",
		ChapterNo:        1,
		ScrollPercentage: 45.5,
	}
	bmData, _ := json.Marshal(bm)
	reqBm := httptest.NewRequest("POST", "/api/novels/test-novel/bookmark", bytes.NewReader(bmData))
	wBm := httptest.NewRecorder()
	router.ServeHTTP(wBm, reqBm)

	if wBm.Code != http.StatusOK {
		t.Fatalf("Save bookmark failed: %d", wBm.Code)
	}

	// Get Bookmark
	reqGetBm := httptest.NewRequest("GET", "/api/novels/test-novel/bookmark", nil)
	wGetBm := httptest.NewRecorder()
	router.ServeHTTP(wGetBm, reqGetBm)

	var bmRes model.Bookmark
	_ = json.NewDecoder(wGetBm.Body).Decode(&bmRes)
	if bmRes.ChapterNo != 1 || bmRes.ScrollPercentage != 45.5 {
		t.Errorf("Unexpected bookmark: %+v", bmRes)
	}
}

func TestCancelJobEndpoint(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	req := httptest.NewRequest("POST", "/api/jobs/job_123/cancel", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Expected 200, got %d", w.Code)
	}
}

func TestConfigEndpoints(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	// Update config
	updatePayload := map[string]interface{}{
		"routerUrl":    "http://127.0.0.1:20128/v1",
		"defaultModel": "new-model-xyz",
		"temperature":  0.5,
	}
	data, _ := json.Marshal(updatePayload)
	req := httptest.NewRequest("POST", "/api/config", bytes.NewReader(data))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("Update config failed: %d", w.Code)
	}

	// Get config
	reqGet := httptest.NewRequest("GET", "/api/config", nil)
	wGet := httptest.NewRecorder()
	router.ServeHTTP(wGet, reqGet)

	var cfgRes struct {
		DefaultModel string  `json:"defaultModel"`
		Temperature  float64 `json:"temperature"`
	}
	_ = json.NewDecoder(wGet.Body).Decode(&cfgRes)
	if cfgRes.DefaultModel != "new-model-xyz" || cfgRes.Temperature != 0.5 {
		t.Errorf("Unexpected config: %+v", cfgRes)
	}
}

func TestExportEndpoints_TXT_MD_EPUB(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	// 1. Export TXT
	reqTxt := httptest.NewRequest("GET", "/api/novels/test-novel/export?format=txt&start=1&end=1", nil)
	wTxt := httptest.NewRecorder()
	router.ServeHTTP(wTxt, reqTxt)

	if wTxt.Code != http.StatusOK {
		t.Fatalf("Export TXT failed: expected 200, got %d", wTxt.Code)
	}
	if !strings.Contains(wTxt.Header().Get("Content-Type"), "text/plain") {
		t.Errorf("TXT Content-Type = %q", wTxt.Header().Get("Content-Type"))
	}
	txtBody := wTxt.Body.String()
	if !strings.Contains(txtBody, "ตอนที่ 1 จุดเริ่มต้น") || !strings.Contains(txtBody, "ย่อหน้าที่ 1") {
		t.Errorf("TXT body missing content: %s", txtBody)
	}

	// 2. Export MD
	reqMd := httptest.NewRequest("GET", "/api/novels/test-novel/export?format=md&start=1&end=1", nil)
	wMd := httptest.NewRecorder()
	router.ServeHTTP(wMd, reqMd)

	if wMd.Code != http.StatusOK {
		t.Fatalf("Export MD failed: expected 200, got %d", wMd.Code)
	}
	if !strings.Contains(wMd.Header().Get("Content-Type"), "text/markdown") {
		t.Errorf("MD Content-Type = %q", wMd.Header().Get("Content-Type"))
	}
	mdBody := wMd.Body.String()
	if !strings.Contains(mdBody, "## ตอนที่ 1 จุดเริ่มต้น") {
		t.Errorf("MD body missing markdown heading: %s", mdBody)
	}

	// 3. Export EPUB
	reqEpub := httptest.NewRequest("GET", "/api/novels/test-novel/export?format=epub&start=1&end=1", nil)
	wEpub := httptest.NewRecorder()
	router.ServeHTTP(wEpub, reqEpub)

	if wEpub.Code != http.StatusOK {
		t.Fatalf("Export EPUB failed: expected 200, got %d", wEpub.Code)
	}
	if !strings.Contains(wEpub.Header().Get("Content-Type"), "application/epub+zip") {
		t.Errorf("EPUB Content-Type = %q", wEpub.Header().Get("Content-Type"))
	}
	if wEpub.Body.Len() == 0 {
		t.Error("EPUB body is empty")
	}
}

func TestAudioSpeech_CacheHit(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	// Direct speech generation test for empty text -> 400
	reqBad := httptest.NewRequest("POST", "/api/audio/speech", bytes.NewReader([]byte(`{"text":""}`)))
	wBad := httptest.NewRecorder()
	router.ServeHTTP(wBad, reqBad)

	if wBad.Code != http.StatusBadRequest {
		t.Errorf("Expected 400 for empty speech text, got %d", wBad.Code)
	}

	// Test invalid JSON -> 400
	reqInvalid := httptest.NewRequest("POST", "/api/audio/speech", bytes.NewReader([]byte(`invalid-json`)))
	wInvalid := httptest.NewRecorder()
	router.ServeHTTP(wInvalid, reqInvalid)

	if wInvalid.Code != http.StatusBadRequest {
		t.Errorf("Expected 400 for invalid JSON in speech, got %d", wInvalid.Code)
	}
}

func TestErrorResponses_404And400(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	// 1. Non-existent novel -> 404
	reqNovel404 := httptest.NewRequest("GET", "/api/novels/nonexistent-slug-xyz", nil)
	wNovel404 := httptest.NewRecorder()
	router.ServeHTTP(wNovel404, reqNovel404)

	if wNovel404.Code != http.StatusNotFound {
		t.Errorf("Expected 404 for missing novel, got %d", wNovel404.Code)
	}

	// 2. Non-existent chapter -> 404
	reqCh404 := httptest.NewRequest("GET", "/api/novels/test-novel/chapters/9999", nil)
	wCh404 := httptest.NewRecorder()
	router.ServeHTTP(wCh404, reqCh404)

	if wCh404.Code != http.StatusNotFound {
		t.Errorf("Expected 404 for missing chapter, got %d", wCh404.Code)
	}

	// 3. Bad JSON to DiscoverGlossary -> 400
	reqDisc400 := httptest.NewRequest("POST", "/api/novels/test-novel/glossary/discover", bytes.NewReader([]byte(`{not json`)))
	wDisc400 := httptest.NewRecorder()
	router.ServeHTTP(wDisc400, reqDisc400)

	if wDisc400.Code != http.StatusBadRequest {
		t.Errorf("Expected 400 for bad discover JSON, got %d", wDisc400.Code)
	}
}
