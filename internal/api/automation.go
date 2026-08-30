package api

// Automatic intelligence: after a fresh import the AI discovers glossary
// terms on its own; after a translation job the AI refreshes story memory
// (summary, characters, facts). Results are merged into the stored files —
// manual edits always win — and announced over the existing SSE channel.

import (
	"context"
	"fmt"
	"log"
	"time"

	"novelclaw/internal/model"
	"novelclaw/internal/translator"
)

const autoIntelTimeout = 3 * time.Minute

// AutoDiscoverGlossary scans the first readable source chapters of a novel
// with the entity-discovery prompt and merges new terms into the glossary.
// Fire-and-forget: an LLM failure must never fail the import that triggered it.
func (h *APIHandler) AutoDiscoverGlossary(slug string) {
	// ponytail: one goroutine per import, no work queue — add one when
	// parallel imports of several novels actually happen.
	go func() {
		defer func() {
			if rec := recover(); rec != nil {
				log.Printf("auto glossary discovery panic (%s): %v", slug, rec)
			}
		}()

		chapters, err := h.store.ListChapters(slug)
		if err != nil {
			log.Printf("auto glossary discovery: list chapters %s: %v", slug, err)
			return
		}
		var sample []model.ChapterMeta
		for _, meta := range chapters {
			if meta.HasSource {
				sample = append(sample, meta)
				if len(sample) >= 3 {
					break
				}
			}
		}
		if len(sample) == 0 {
			return
		}
		var paragraphs []string
		for _, meta := range sample {
			ch, err := h.store.GetChapter(slug, meta.ChapterNo)
			if err != nil {
				continue // tolerate individual unreadable chapters
			}
			paragraphs = append(paragraphs, ch.SourceText...)
		}
		if len(paragraphs) == 0 {
			return
		}
		title := slug
		if novel, err := h.store.GetNovel(slug); err == nil && novel.Title != "" {
			title = novel.Title
		}
		provider, modelName, err := h.resolveIntelligenceProvider("", "")
		if err != nil {
			log.Printf("auto glossary discovery: provider: %v", err)
			return
		}
		ctx, cancel := context.WithTimeout(context.Background(), autoIntelTimeout)
		defer cancel()
		discovered, err := h.translator.DiscoverGlossaryTerms(ctx, title, paragraphs, modelName)
		if err != nil {
			log.Printf("auto glossary discovery (%s via %s): %v", slug, provider.ID, err)
			return
		}
		added, err := h.mergeDiscoveredGlossary(slug, discovered)
		if err != nil {
			log.Printf("auto glossary discovery: merge %s: %v", slug, err)
			return
		}
		if added == 0 {
			return
		}
		h.sse.Broadcast(map[string]interface{}{
			"type":      "auto_intelligence",
			"novelSlug": slug,
			"kind":      "glossary",
			"message":   fmt.Sprintf("AI สแกนหาชื่อเฉพาะอัตโนมัติ — เพิ่ม %d ศัพท์ใหม่เข้าคลังศัพท์แล้ว", added),
			"added":     added,
		})
	}()
}

// mergeDiscoveredGlossary adds only genuinely new terms; existing entries in
// the stored glossary (manual entries and corrections) always win. Returns
// how many terms were added.
func (h *APIHandler) mergeDiscoveredGlossary(slug string, discovered []model.GlossaryItem) (int, error) {
	if len(discovered) == 0 {
		return 0, nil
	}
	glossary, err := h.store.GetGlossary(slug)
	if err != nil {
		return 0, err
	}
	termMap := make(map[string]bool, len(glossary.Terms))
	for _, t := range glossary.Terms {
		termMap[t.Term] = true
	}
	added := 0
	for _, d := range discovered {
		if d.Term == "" || d.Target == "" || termMap[d.Term] {
			continue
		}
		glossary.Terms = append(glossary.Terms, d)
		termMap[d.Term] = true
		added++
	}
	if added == 0 {
		return 0, nil
	}
	return added, h.store.SaveGlossary(glossary)
}

// AutoGenerateMemory summarizes the most recent translated chapters into the
// novel memory (story summary, characters, facts) and merges the candidate
// into what already exists. Fire-and-forget like glossary discovery.
func (h *APIHandler) AutoGenerateMemory(slug string) {
	go func() {
		defer func() {
			if rec := recover(); rec != nil {
				log.Printf("auto memory generation panic (%s): %v", slug, rec)
			}
		}()

		chapters, err := h.store.ListChapters(slug)
		if err != nil {
			log.Printf("auto memory generation: list chapters %s: %v", slug, err)
			return
		}
		var eligible []model.ChapterMeta
		for _, meta := range chapters {
			if meta.HasTranslated {
				eligible = append(eligible, meta)
			}
		}
		if len(eligible) == 0 {
			return
		}
		window := 5
		if len(eligible) < window {
			window = len(eligible)
		}
		selected := eligible[len(eligible)-window:]
		glossary, err := h.store.GetGlossary(slug)
		if err != nil {
			log.Printf("auto memory generation: glossary %s: %v", slug, err)
			return
		}
		contextText, used, err := h.buildMemoryGenerationContext(slug, selected, glossary)
		if err != nil || used == 0 {
			log.Printf("auto memory generation: context %s (used=%d): %v", slug, used, err)
			return
		}
		existing, err := h.store.GetNovelMemory(slug)
		if err != nil {
			log.Printf("auto memory generation: memory %s: %v", slug, err)
			return
		}
		provider, modelName, err := h.resolveIntelligenceProvider("", "")
		if err != nil {
			log.Printf("auto memory generation: provider: %v", err)
			return
		}
		systemPrompt, userPrompt := translator.BuildMemoryExtractionPrompts(existing, contextText)
		ctx, cancel := context.WithTimeout(context.Background(), autoIntelTimeout)
		defer cancel()
		raw, _, err := h.translator.CompleteWithFallbackForProvider(ctx, provider, systemPrompt, userPrompt, []string{modelName}, 0.15)
		if err != nil {
			log.Printf("auto memory generation (%s via %s): %v", slug, provider.ID, err)
			return
		}
		candidate, err := translator.ParseNovelMemoryCandidate(raw)
		if err != nil {
			log.Printf("auto memory generation: parse %s: %v", slug, err)
			return
		}
		candidate.NovelSlug = slug
		merged := translator.MergeNovelMemory(existing, candidate)
		merged.NovelSlug = slug
		if err := h.store.SaveNovelMemory(merged); err != nil {
			log.Printf("auto memory generation: save %s: %v", slug, err)
			return
		}
		h.sse.Broadcast(map[string]interface{}{
			"type":         "auto_intelligence",
			"novelSlug":    slug,
			"kind":         "memory",
			"message":      "AI สรุปเนื้อเรื่องและตัวละคร อัปเดต Story Memory อัตโนมัติแล้ว",
			"chaptersUsed": used,
		})
	}()
}
