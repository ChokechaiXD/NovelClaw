package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"novelclaw/internal/model"
)

func TestMemoryRoundTrip(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	payload := model.NovelMemory{
		StorySummary: "ตัวเอกกำลังสร้างดินแดนในโลกใหม่",
		Characters: []model.CharacterMemory{{
			SourceName: "曹星", ThaiName: "เฉาซิง", Role: "ตัวเอก", Pronouns: "เขา",
		}},
		Facts: []string{"เฉาซิงเป็นเจ้าของดินแดน"},
	}
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(http.MethodPost, "/api/novels/test-novel/memory", bytes.NewReader(body))
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("save memory: got %d body=%s", w.Code, w.Body.String())
	}

	req = httptest.NewRequest(http.MethodGet, "/api/novels/test-novel/memory", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("get memory: got %d", w.Code)
	}
	var got model.NovelMemory
	if err := json.NewDecoder(w.Body).Decode(&got); err != nil {
		t.Fatal(err)
	}
	if got.NovelSlug != "test-novel" || got.StorySummary != payload.StorySummary {
		t.Fatalf("unexpected memory: %+v", got)
	}
	if len(got.Characters) != 1 || got.Characters[0].ThaiName != "เฉาซิง" {
		t.Fatalf("unexpected characters: %+v", got.Characters)
	}
}

func TestQARebuildAndRead(t *testing.T) {
	_, _, router, cleanup := setupTestEnv(t)
	defer cleanup()

	req := httptest.NewRequest(http.MethodPost, "/api/novels/test-novel/qa/rebuild", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("rebuild QA: got %d body=%s", w.Code, w.Body.String())
	}
	var rebuilt struct {
		Rebuilt int                              `json:"rebuilt"`
		Reports []model.TranslationQualityReport `json:"reports"`
	}
	if err := json.NewDecoder(w.Body).Decode(&rebuilt); err != nil {
		t.Fatal(err)
	}
	if rebuilt.Rebuilt != 1 || len(rebuilt.Reports) != 1 {
		t.Fatalf("unexpected rebuild result: %+v", rebuilt)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/novels/test-novel/qa/1", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("get QA: got %d body=%s", w.Code, w.Body.String())
	}
	var report model.TranslationQualityReport
	if err := json.NewDecoder(w.Body).Decode(&report); err != nil {
		t.Fatal(err)
	}
	if report.ChapterNo != 1 || report.Score <= 0 {
		t.Fatalf("unexpected QA report: %+v", report)
	}
}

func TestJobCountersTakeErrorClearsSafely(t *testing.T) {
	jc := &jobCounters{}
	jc.setError("boom")
	if got := jc.takeError(); got != "boom" {
		t.Fatalf("takeError() = %q, want boom", got)
	}
	if got := jc.takeError(); got != "" {
		t.Fatalf("second takeError() = %q, want empty", got)
	}
}

func TestGenerateMemoryCandidatePreviewsWithoutSaving(t *testing.T) {
	cfg, _, router, cleanup := setupTestEnv(t)
	defer cleanup()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"choices": []interface{}{map[string]interface{}{"message": map[string]string{
				"content": `{"storySummary":"fresh summary","characters":[],"facts":["fact"]}`,
			}}},
		})
	}))
	defer server.Close()
	key := "dummy"
	if err := cfg.ConfigureProvider("custom", server.URL, &key, "memory-model", "openai-chat", true); err != nil {
		t.Fatal(err)
	}
	body := bytes.NewBufferString(`{"startChapter":1,"endChapter":1}`)
	req := httptest.NewRequest(http.MethodPost, "/api/novels/test-novel/memory/generate", body)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("generate memory: status=%d body=%s", w.Code, w.Body.String())
	}
	var res struct {
		Merged model.NovelMemory `json:"merged"`
	}
	if err := json.NewDecoder(w.Body).Decode(&res); err != nil {
		t.Fatal(err)
	}
	if res.Merged.StorySummary != "fresh summary" {
		t.Fatalf("unexpected merged memory: %+v", res.Merged)
	}
	req = httptest.NewRequest(http.MethodGet, "/api/novels/test-novel/memory", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	var stored model.NovelMemory
	_ = json.NewDecoder(w.Body).Decode(&stored)
	if stored.StorySummary != "" {
		t.Fatalf("preview unexpectedly persisted memory: %+v", stored)
	}
}

func TestQARepairWithAISavesOnlyImprovedCandidate(t *testing.T) {
	cfg, store, router, cleanup := setupTestEnv(t)
	defer cleanup()
	if err := store.SaveChapter("test-novel", 1, "source", "old", []string{"100 coins", "second"}, []string{"90 เหรียญ", "ย่อหน้าสอง"}); err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"choices": []interface{}{map[string]interface{}{"message": map[string]string{
				"content": `{"title":"fixed","paragraphs":["100 เหรียญ","ย่อหน้าสอง"]}`,
			}}},
		})
	}))
	defer server.Close()
	key := "dummy"
	if err := cfg.ConfigureProvider("custom", server.URL, &key, "repair-model", "openai-chat", true); err != nil {
		t.Fatal(err)
	}
	body := bytes.NewBufferString(`{"targetScore":100}`)
	req := httptest.NewRequest(http.MethodPost, "/api/novels/test-novel/qa/1/repair", body)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("QA repair: status=%d body=%s", w.Code, w.Body.String())
	}
	var res struct {
		Saved          bool `json:"saved"`
		CandidateScore int  `json:"candidateScore"`
	}
	if err := json.NewDecoder(w.Body).Decode(&res); err != nil {
		t.Fatal(err)
	}
	if !res.Saved || res.CandidateScore != 100 {
		t.Fatalf("unexpected repair result: %+v body=%s", res, w.Body.String())
	}
	chapter, err := store.GetChapter("test-novel", 1)
	if err != nil {
		t.Fatal(err)
	}
	if len(chapter.TranslatedText) != 2 || chapter.TranslatedText[0] != "100 เหรียญ" {
		t.Fatalf("improved candidate not persisted: %+v", chapter.TranslatedText)
	}
}
