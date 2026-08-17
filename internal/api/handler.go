package api

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"slices"
	"strconv"
	"strings"
	"sync"
	"time"

	"novelclaw/internal/config"
	"novelclaw/internal/model"
	"novelclaw/internal/scraper"
	"novelclaw/internal/storage"
	"novelclaw/internal/translator"
)

// APIHandler coordinates API requests
type APIHandler struct {
	cfg        *config.AppConfig
	store      *storage.Store
	scraper    *scraper.UniversalScraper
	translator *translator.Client
	sse        *SSEBroker
	jobsMu     sync.Mutex
	activeJobs map[string]*model.TranslationProgress
	cancels    map[string]context.CancelFunc
}

// NewAPIHandler initializes API handlers
func NewAPIHandler(cfg *config.AppConfig, store *storage.Store, sse *SSEBroker) *APIHandler {
	return &APIHandler{
		cfg:        cfg,
		store:      store,
		scraper:    scraper.NewUniversalScraper(),
		translator: translator.NewClient(cfg),
		sse:        sse,
		activeJobs: make(map[string]*model.TranslationProgress),
		cancels:    make(map[string]context.CancelFunc),
	}
}

// safeSlug sanitizes a URL path slug to prevent path traversal and HTML
// attribute injection. Only [A-Za-z0-9_-] survive, so "..", separators and
// quotes are impossible in the result.
func safeSlug(raw string) string {
	var b strings.Builder
	for _, r := range raw {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '-' || r == '_' {
			b.WriteRune(r)
		}
	}
	raw = strings.TrimSpace(b.String())
	if raw == "" {
		return "_invalid_"
	}
	return raw
}

// WriteJSON sends a standard JSON response
func WriteJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

// WriteError sends a JSON error response
func WriteError(w http.ResponseWriter, status int, message string) {
	WriteJSON(w, status, map[string]string{"error": message})
}

// ListNovels returns all novels
func (h *APIHandler) ListNovels(w http.ResponseWriter, r *http.Request) {
	novels, err := h.store.ListNovels()
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"novels": novels,
	})
}

// GetNovel returns a single novel
func (h *APIHandler) GetNovel(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	novel, err := h.store.GetNovel(slug)
	if err != nil {
		WriteError(w, http.StatusNotFound, err.Error())
		return
	}
	WriteJSON(w, http.StatusOK, novel)
}

// SaveNovel creates or updates a novel
func (h *APIHandler) SaveNovel(w http.ResponseWriter, r *http.Request) {
	var n model.Novel
	if err := json.NewDecoder(r.Body).Decode(&n); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid payload")
		return
	}
	if err := h.store.SaveNovel(&n); err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	WriteJSON(w, http.StatusOK, n)
}

// ListChapters returns the chapter list for a novel
func (h *APIHandler) ListChapters(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	chapters, err := h.store.ListChapters(slug)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"chapters": chapters,
	})
}

// GetChapter returns a single chapter's content
func (h *APIHandler) GetChapter(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	numStr := r.PathValue("num")
	chNum, err := strconv.Atoi(numStr)
	if err != nil || chNum <= 0 {
		WriteError(w, http.StatusBadRequest, "Invalid chapter number")
		return
	}

	chapter, err := h.store.GetChapter(slug, chNum)
	if err != nil {
		WriteError(w, http.StatusNotFound, err.Error())
		return
	}

	// Automatic Zero-Hanzi Interceptor on reading
	if len(chapter.TranslatedText) > 0 {
		hasAnyHanzi := translator.HasHanzi(chapter.TranslatedTitle)
		if !hasAnyHanzi {
			for _, p := range chapter.TranslatedText {
				if translator.HasHanzi(p) {
					hasAnyHanzi = true
					break
				}
			}
		}
		if hasAnyHanzi {
			glossary, _ := h.store.GetGlossary(slug)
			var gMap map[string]string
			if glossary != nil && len(glossary.Terms) > 0 {
				gMap = make(map[string]string)
				for _, t := range glossary.Terms {
					gMap[t.Term] = t.Target
				}
			}
			chapter.TranslatedTitle = translator.SanitizeText(chapter.TranslatedTitle, gMap)
			chapter.TranslatedText = translator.SanitizeParagraphs(chapter.TranslatedText, gMap)
			_ = h.store.SaveChapter(slug, chNum, chapter.SourceTitle, chapter.TranslatedTitle, nil, chapter.TranslatedText)
		}
	}

	WriteJSON(w, http.StatusOK, chapter)
}

// GetGlossary returns glossary for a novel
func (h *APIHandler) GetGlossary(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	glossary, err := h.store.GetGlossary(slug)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	WriteJSON(w, http.StatusOK, glossary)
}

// SaveGlossary saves glossary terms for a novel
func (h *APIHandler) SaveGlossary(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	var g model.NovelGlossary
	if err := json.NewDecoder(r.Body).Decode(&g); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid payload")
		return
	}
	g.NovelSlug = slug
	if err := h.store.SaveGlossary(&g); err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	WriteJSON(w, http.StatusOK, g)
}

// DiscoverGlossary scans chapters and extracts terms using LLM
func (h *APIHandler) DiscoverGlossary(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	var req model.DiscoverGlossaryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		WriteJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON payload"})
		return
	}
	req.NovelSlug = slug

	if req.StartChapter <= 0 {
		req.StartChapter = 1
	}
	if req.EndChapter <= 0 {
		req.EndChapter = req.StartChapter + 2
	}

	novel, err := h.store.GetNovel(slug)
	if err != nil {
		WriteError(w, http.StatusNotFound, "Novel not found")
		return
	}

	// Gather sample paragraphs from requested chapters
	var sampleParagraphs []string
	for chNo := req.StartChapter; chNo <= req.EndChapter; chNo++ {
		ch, err := h.store.GetChapter(slug, chNo)
		if err == nil && len(ch.SourceText) > 0 {
			sampleParagraphs = append(sampleParagraphs, ch.SourceText...)
		}
	}

	if len(sampleParagraphs) == 0 {
		WriteError(w, http.StatusBadRequest, "No source chapters available to scan")
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Minute)
	defer cancel()

	discovered, err := h.translator.DiscoverGlossaryTerms(ctx, novel.Title, sampleParagraphs, req.Model)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("Discovery failed: %v", err))
		return
	}

	// Auto-merge into existing glossary
	existing, _ := h.store.GetGlossary(slug)
	termMap := make(map[string]bool)
	for _, t := range existing.Terms {
		termMap[t.Term] = true
	}

	for _, d := range discovered {
		if !termMap[d.Term] && d.Term != "" && d.Target != "" {
			existing.Terms = append(existing.Terms, d)
			termMap[d.Term] = true
		}
	}
	_ = h.store.SaveGlossary(existing)

	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"discovered": discovered,
		"glossary":   existing,
	})
}

// GetBookmark gets bookmark position
func (h *APIHandler) GetBookmark(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	bm, err := h.store.GetBookmark(slug)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	WriteJSON(w, http.StatusOK, bm)
}

// SaveBookmark saves bookmark position
func (h *APIHandler) SaveBookmark(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	var bm model.Bookmark
	if err := json.NewDecoder(r.Body).Decode(&bm); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid payload")
		return
	}
	bm.NovelSlug = slug
	if err := h.store.SaveBookmark(&bm); err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	WriteJSON(w, http.StatusOK, bm)
}

// Import handles importing from URL or raw pasted text
func (h *APIHandler) Import(w http.ResponseWriter, r *http.Request) {
	var req model.ImportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid payload")
		return
	}

	// Case 1: Manual Paste
	if req.RawContent != "" {
		if req.NovelSlug == "" {
			WriteError(w, http.StatusBadRequest, "novelSlug is required for raw paste")
			return
		}

		// Ensure novel exists or create it
		if _, err := h.store.GetNovel(req.NovelSlug); err != nil {
			novelTitle := req.Title
			if novelTitle == "" {
				novelTitle = req.NovelSlug
			}
			_ = h.store.SaveNovel(&model.Novel{
				Slug:       req.NovelSlug,
				Title:      novelTitle,
				Genre:      req.Genre,
				SourceLang: "cn",
				TargetLang: "th",
				UpdatedAt:  time.Now(),
			})
		}

		chNum := req.StartChapter
		if chNum <= 0 {
			existingChapters, err := h.store.ListChapters(req.NovelSlug)
			if err == nil && len(existingChapters) > 0 {
				chNum = existingChapters[len(existingChapters)-1].ChapterNo + 1
			} else {
				chNum = 1
			}
		}

		lines := strings.Split(req.RawContent, "\n")
		var paragraphs []string
		for _, l := range lines {
			t := strings.TrimSpace(l)
			if t != "" {
				paragraphs = append(paragraphs, t)
			}
		}

		chTitle := req.Title
		if chTitle == "" {
			chTitle = fmt.Sprintf("ตอนที่ %d", chNum)
		}

		err := h.store.SaveChapter(req.NovelSlug, chNum, chTitle, "", paragraphs, nil)
		if err != nil {
			WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}

		WriteJSON(w, http.StatusOK, map[string]interface{}{
			"success":   true,
			"chapterNo": chNum,
			"message":   fmt.Sprintf("บันทึกตอนที่ %d เรียบร้อยแล้ว", chNum),
		})
		return
	}

	// Case 2: URL Import
	if req.URL == "" {
		WriteError(w, http.StatusBadRequest, "URL or rawContent is required")
		return
	}

	go func() {
		chapter, err := h.scraper.FetchChapter(req.URL)
		if err == nil && len(chapter.Paragraphs) > 0 {
			slug := req.NovelSlug
			if slug == "" {
				slug = "imported-novel"
			}
			if _, err := h.store.GetNovel(slug); err != nil {
				_ = h.store.SaveNovel(&model.Novel{
					Slug:       slug,
					Title:      chapter.Title,
					Genre:      req.Genre,
					SourceLang: "cn",
					TargetLang: "th",
					UpdatedAt:  time.Now(),
				})
			}

			chNum := chapter.ChapterNo
			if chNum <= 0 {
				existingChapters, _ := h.store.ListChapters(slug)
				chNum = len(existingChapters) + 1
			}

			_ = h.store.SaveChapter(slug, chNum, chapter.Title, "", chapter.Paragraphs, nil)
			h.sse.Broadcast(map[string]interface{}{
				"type":      "import_done",
				"novelSlug": slug,
				"chapterNo": chNum,
			})
			return
		}

		toc, err := h.scraper.FetchTOC(req.URL)
		if err == nil && len(toc.Chapters) > 0 {
			slug := req.NovelSlug
			if slug == "" {
				slug = sanitizeSlug(toc.Title)
			}

			_ = h.store.SaveNovel(&model.Novel{
				Slug:        slug,
				Title:       toc.Title,
				Author:      toc.Author,
				Genre:       req.Genre,
				Description: toc.Description,
				CoverURL:    toc.CoverURL,
				SourceLang:  "cn",
				TargetLang:  "th",
			})

			start := 1
			if req.StartChapter > 0 {
				start = req.StartChapter
			}
			end := len(toc.Chapters)
			if req.EndChapter > 0 && req.EndChapter < end {
				end = req.EndChapter
			}

			for i := start - 1; i < end && i < len(toc.Chapters); i++ {
				chItem := toc.Chapters[i]
				ch, err := h.scraper.FetchChapter(chItem.URL)
				if err == nil && len(ch.Paragraphs) > 0 {
					_ = h.store.SaveChapter(slug, chItem.ChapterNo, ch.Title, "", ch.Paragraphs, nil)
				}
				h.sse.Broadcast(map[string]interface{}{
					"type":      "import_progress",
					"novelSlug": slug,
					"current":   i + 1,
					"total":     end,
					"title":     chItem.Title,
				})
				time.Sleep(400 * time.Millisecond)
			}

			h.sse.Broadcast(map[string]interface{}{
				"type":      "import_done",
				"novelSlug": slug,
				"total":     end,
			})
			return
		}

		h.sse.Broadcast(map[string]interface{}{
			"type":    "import_error",
			"message": "นำเข้าล้มเหลว: URL นี้อ่านไมได้ ทังรายตอนและสารบัญ",
		})
	}()

	WriteJSON(w, http.StatusAccepted, map[string]interface{}{
		"status":  "import_started",
		"message": "Import job started in background",
	})
}

// CancelJob stops an active background translation job
func (h *APIHandler) CancelJob(w http.ResponseWriter, r *http.Request) {
	jobID := r.PathValue("id")
	h.jobsMu.Lock()
	var slug string
	if p, ok := h.activeJobs[jobID]; ok {
		slug = p.NovelSlug
	}
	// Cancelling one job stops every queued/running job of the same novel,
	// so a single "stop" button really stops the whole queue.
	for id, p := range h.activeJobs {
		if cancel, ok := h.cancels[id]; ok && (slug == "" && id == jobID || slug != "" && p.NovelSlug == slug) {
			cancel()
			delete(h.cancels, id)
		}
	}
	h.jobsMu.Unlock()

	h.sse.Broadcast(model.TranslationProgress{
		JobID:   jobID,
		Status:  "cancelled",
		Message: "ยกเลิกการแปลเรียบร้อยแล้ว",
	})

	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"jobId":   jobID,
	})
}

// Translate handles translating chapters with smart chunking and genre presets
func (h *APIHandler) Translate(w http.ResponseWriter, r *http.Request) {
	var req model.TranslateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid payload")
		return
	}

	if req.NovelSlug == "" {
		WriteError(w, http.StatusBadRequest, "novelSlug is required")
		return
	}

	// Persist selected model permanently if provided
	if req.Model != "" && req.Model != h.cfg.GetDefaultModel() {
		_ = h.cfg.Update(func(c *config.AppConfig) {
			c.DefaultModel = req.Model
		})
	}

	if req.StartChapter <= 0 {
		req.StartChapter = 1
	}
	if req.EndChapter <= 0 || req.EndChapter < req.StartChapter {
		req.EndChapter = req.StartChapter
	}

	jobID := fmt.Sprintf("job_%d", time.Now().UnixNano())
	jobCtx, cancel := context.WithCancel(context.Background())

	h.jobsMu.Lock()
	h.cancels[jobID] = cancel
	h.activeJobs[jobID] = &model.TranslationProgress{
		JobID:          jobID,
		NovelSlug:      req.NovelSlug,
		TotalChapters:  req.EndChapter,
		CurrentChapter: req.StartChapter,
		Status:         "running",
		Percentage:     0,
	}
	h.jobsMu.Unlock()

	// Start translation worker in background
	go h.runTranslationJob(jobCtx, jobID, req)

	WriteJSON(w, http.StatusAccepted, map[string]interface{}{
		"jobId":   jobID,
		"status":  "translation_started",
		"message": fmt.Sprintf("Translating chapters %d - %d", req.StartChapter, req.EndChapter),
	})
}

func (h *APIHandler) runTranslationJob(ctx context.Context, jobID string, req model.TranslateRequest) {
	defer func() {
		h.jobsMu.Lock()
		delete(h.cancels, jobID)
		delete(h.activeJobs, jobID)
		h.jobsMu.Unlock()
	}()

	novel, _ := h.store.GetNovel(req.NovelSlug)
	genre := req.Genre
	if genre == "" && novel != nil {
		genre = novel.Genre
	}

	glossary, _ := h.store.GetGlossary(req.NovelSlug)
	styleRules, _ := h.store.GetStyleRules(req.NovelSlug)
	chapterList, _ := h.store.ListChapters(req.NovelSlug)
	total := req.EndChapter - req.StartChapter + 1

	// Model fallback chain: primary model first, then any fallbacks the UI
	// sent (e.g. other models from the same gateway). A dead model in the
	// chain can no longer kill the whole queue.
	modelChain := []string{req.Model}
	for _, m := range req.FallbackModels {
		if m != "" && m != req.Model && !slices.Contains(modelChain, m) {
			modelChain = append(modelChain, m)
		}
	}
	successCount := 0
	var lastError string

	for chNo := req.StartChapter; chNo <= req.EndChapter; chNo++ {
		select {
		case <-ctx.Done():
			log.Printf("Translation job %s cancelled by user\n", jobID)
			return
		default:
		}

		currentIdx := chNo - req.StartChapter + 1
		pct := int((float64(currentIdx) / float64(total)) * 100)

		h.sse.Broadcast(model.TranslationProgress{
			JobID:          jobID,
			NovelSlug:      req.NovelSlug,
			CurrentChapter: chNo,
			TotalChapters:  req.EndChapter,
			Status:         "running",
			Message:        fmt.Sprintf("กำลังแปลตอนที่ %d... (%d/%d)", chNo, currentIdx, total),
			Percentage:     pct,
		})

		content, err := h.store.GetChapter(req.NovelSlug, chNo)
		if err != nil || len(content.SourceText) == 0 {
			log.Printf("Chapter %d has no source text, skipping\n", chNo)
			continue
		}

		if len(content.TranslatedText) > 0 && !req.Force {
			log.Printf("Chapter %d already translated, skipping\n", chNo)
			successCount++
			continue
		}

		// Previous context: last 3 paragraphs of the nearest preceding chapter
		// (gap-aware: chapter numbers can skip, e.g. 72 -> 86)
		var prevContext string
		if prevNo := previousChapterNo(chapterList, chNo); prevNo > 0 {
			if prevCh, err := h.store.GetChapter(req.NovelSlug, prevNo); err == nil && len(prevCh.TranslatedText) > 0 {
				n := len(prevCh.TranslatedText)
				if n > 3 {
					n = 3
				}
				tail := prevCh.TranslatedText[len(prevCh.TranslatedText)-n:]
				prevContext = fmt.Sprintf("ตอนก่อนหน้า (%s) จบด้วย:\n%s", prevCh.TranslatedTitle, strings.Join(tail, "\n"))
			}
		}

		relevantGlossary := translator.FilterRelevantGlossary(glossary, content.SourceText)
		systemPrompt := translator.BuildSystemPrompt(relevantGlossary, prevContext, genre, styleRules)

		// Smart Chunking for long chapters (max 25 paragraphs or 750 chars per chunk)
		chunks := translator.SplitParagraphsIntoChunks(content.SourceText, 750)
		var fullTranslatedParagraphs []string
		var finalTransTitle string
		chapterFailed := false

		for chunkIdx, chunk := range chunks {
			select {
			case <-ctx.Done():
				return
			default:
			}

			chunkUserPrompt := translator.BuildUserPrompt(content.SourceTitle, chunk.Paragraphs)
			if chunkIdx > 0 && len(fullTranslatedParagraphs) > 0 {
				lastChunkEnd := fullTranslatedParagraphs[len(fullTranslatedParagraphs)-1]
				chunkUserPrompt = fmt.Sprintf("[เนื้อหาก่อนหน้านี้ในบทเดียวกัน: ...%s]\n\n%s", lastChunkEnd, chunkUserPrompt)
			}

			chunkCtx, chunkCancel := context.WithTimeout(ctx, 120*time.Second)
			rawOutput, _, err := h.translator.CompleteWithFallback(chunkCtx, systemPrompt, chunkUserPrompt, modelChain, req.Temperature)
			chunkCancel()

			if err != nil {
				lastError = err.Error()
				log.Printf("Translation error on chapter %d (chunk %d): %v\n", chNo, chunkIdx, err)
				h.sse.Broadcast(model.TranslationProgress{
					JobID:          jobID,
					NovelSlug:      req.NovelSlug,
					CurrentChapter: chNo,
					Status:         "error",
					Message:        fmt.Sprintf("ข้อผิดพลาดตอนที่ %d: %v", chNo, err),
					ErrorDetails:   err.Error(),
				})
				chapterFailed = true
				break
			}

			tTitle, tParagraphs := translator.ParseTranslationOutput(rawOutput)
			if finalTransTitle == "" && tTitle != "" {
				finalTransTitle = tTitle
			}
			fullTranslatedParagraphs = append(fullTranslatedParagraphs, tParagraphs...)
		}

		if chapterFailed || len(fullTranslatedParagraphs) == 0 {
			continue
		}

		if finalTransTitle == "" {
			finalTransTitle = fmt.Sprintf("ตอนที่ %d", chNo)
		}

		var gMap map[string]string
		if glossary != nil && len(glossary.Terms) > 0 {
			gMap = make(map[string]string)
			for _, t := range glossary.Terms {
				gMap[t.Term] = t.Target
			}
		}
		finalTransTitle = translator.SanitizeText(finalTransTitle, gMap)
		fullTranslatedParagraphs = translator.SanitizeParagraphs(fullTranslatedParagraphs, gMap)

		// Consistency check: glossary terms present in the source should have
		// their expected target somewhere in the translation. Mismatches are
		// reported (not blocking) so the user can confirm glossary entries.
		var warnings []string
		if glossary != nil && len(glossary.Terms) > 0 {
			srcJoined := strings.Join(content.SourceText, "\n")
			thJoined := strings.Join(fullTranslatedParagraphs, "\n")
			seenTerm := map[string]bool{}
			for _, t := range glossary.Terms {
				if t.Term == "" || t.Target == "" || seenTerm[t.Term] {
					continue
				}
				seenTerm[t.Term] = true
				if strings.Contains(srcJoined, t.Term) && !strings.Contains(thJoined, t.Target) {
					warnings = append(warnings, fmt.Sprintf("พบ %q แต่ไม่พบ %q ในฉบับแปล", t.Term, t.Target))
					if len(warnings) >= 5 {
						break
					}
				}
			}
		}

		_ = h.store.SaveChapter(req.NovelSlug, chNo, content.SourceTitle, finalTransTitle, nil, fullTranslatedParagraphs)
		successCount++

		h.sse.Broadcast(map[string]interface{}{
			"type":      "chapter_translated",
			"novelSlug": req.NovelSlug,
			"chapterNo": chNo,
			"title":     finalTransTitle,
			"warnings":  warnings,
		})
	}

	finalStatus := "completed"
	finalMsg := fmt.Sprintf("การแปลเสร็จสิ้น (%d/%d ตอน)", successCount, total)
	if successCount == 0 && lastError != "" {
		finalStatus = "error"
		finalMsg = fmt.Sprintf("การแปลล้มเหลว: %s", lastError)
	}

	h.sse.Broadcast(model.TranslationProgress{
		JobID:        jobID,
		NovelSlug:    req.NovelSlug,
		Status:       finalStatus,
		Message:      finalMsg,
		Percentage:   100,
		ErrorDetails: lastError,
	})
}

// ListModels returns active models from 9Router/OpenRouter
func (h *APIHandler) ListModels(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()

	models, err := h.translator.FetchModels(ctx)
	if err != nil {
		WriteError(w, http.StatusBadGateway, fmt.Sprintf("Failed to fetch models: %v", err))
		return
	}

	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"models": models,
	})
}

// GetConfig returns current runtime configuration. The API key is masked so
// it is never exposed through the API surface.
func (h *APIHandler) GetConfig(w http.ResponseWriter, r *http.Request) {
	type safeConfig struct {
		Port         int     `json:"port"`
		Host         string  `json:"host"`
		DataDir      string  `json:"dataDir"`
		RouterURL    string  `json:"routerUrl"`
		APIKey       string  `json:"apiKey"`
		DefaultModel string  `json:"defaultModel"`
		Temperature  float64 `json:"temperature"`
		Parallel     int     `json:"parallel"`
		Provider     string  `json:"provider,omitempty"`
	}
	WriteJSON(w, http.StatusOK, safeConfig{
		Port:         h.cfg.Port,
		Host:         h.cfg.Host,
		DataDir:      h.cfg.DataDir,
		RouterURL:    h.cfg.GetRouterURL(),
		APIKey:       h.cfg.MaskedAPIKey(),
		DefaultModel: h.cfg.GetDefaultModel(),
		Temperature:  h.cfg.GetTemperature(),
		Parallel:     h.cfg.Parallel,
		Provider:     h.cfg.GetProvider(),
	})
}

// UpdateConfig updates runtime configuration. An empty apiKey field keeps the
// existing key (the frontend receives only the masked value, so echoing it
// back must not overwrite the real key).
func (h *APIHandler) UpdateConfig(w http.ResponseWriter, r *http.Request) {
	var payload map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		WriteError(w, http.StatusBadRequest, fmt.Sprintf("Invalid configuration: %v", err))
		return
	}

	if err := h.cfg.Update(func(c *config.AppConfig) {
		if val, ok := payload["routerUrl"].(string); ok && val != "" {
			c.RouterURL = val
		}
		if val, ok := payload["defaultModel"].(string); ok && val != "" {
			c.DefaultModel = val
		}
		if val, ok := payload["apiKey"].(string); ok && val != "" {
			c.APIKey = val
		}
		if val, ok := payload["temperature"].(float64); ok && val >= 0 && val <= 2 {
			c.Temperature = val
		}
		if val, ok := payload["provider"].(string); ok {
			c.Provider = val
		}
	}); err != nil {
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to save config: %v", err))
		return
	}
	h.GetConfig(w, r)
}

// DetectProviders probes well-known local LLM gateways and returns the ones
// that answer on /v1/models, so the settings UI can offer one-click setup
// instead of asking the user to type URLs and keys manually.
func (h *APIHandler) DetectProviders(w http.ResponseWriter, r *http.Request) {
	type probe struct {
		Provider   string `json:"provider"`
		URL        string `json:"url"`
		ModelCount int    `json:"modelCount"`
	}
	var found []probe
	candidates := []struct{ name, url string }{
		{"9router", "http://localhost:20128/v1/models"},
		{"ollama", "http://localhost:11434/v1/models"},
		{"lmstudio", "http://localhost:1234/v1/models"},
		{"vllm", "http://localhost:8000/v1/models"},
	}
	client := &http.Client{Timeout: 700 * time.Millisecond}
	for _, c := range candidates {
		resp, err := client.Get(c.url) //nolint:gosec // localhost probe only
		if err != nil {
			continue
		}
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			continue
		}
		count := 0
		var ml struct {
			Data []json.RawMessage `json:"data"`
		}
		if json.Unmarshal(body, &ml) == nil {
			count = len(ml.Data)
		}
		found = append(found, probe{Provider: c.name, URL: c.url, ModelCount: count})
	}
	WriteJSON(w, http.StatusOK, map[string]interface{}{"providers": found})
}

func sanitizeSlug(s string) string {
	s = strings.ToLower(strings.TrimSpace(s))
	s = strings.ReplaceAll(s, " ", "-")
	var result strings.Builder
	for _, r := range s {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '-' || r == '_' {
			result.WriteRune(r)
		}
	}
	if result.Len() == 0 {
		return fmt.Sprintf("novel-%d", time.Now().Unix())
	}
	return result.String()
}

// previousChapterNo returns the largest chapter number strictly below chNo,
// or 0 when none exists. Handles gaps in chapter numbering.
func previousChapterNo(chapters []model.ChapterMeta, chNo int) int {
	prev := 0
	for _, ch := range chapters {
		if ch.ChapterNo < chNo && ch.ChapterNo > prev {
			prev = ch.ChapterNo
		}
	}
	return prev
}
