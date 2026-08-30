package storage

import (
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"time"

	"novelclaw/internal/model"
)

// scheduleNovelStatsUpdate resets a per-novel timer so a burst of chapter
// writes results in one stats scan instead of one goroutine/scan per write.
func (s *Store) scheduleNovelStatsUpdate(slug string) {
	slug = pathSafeSlug(slug)
	s.statsMu.Lock()
	defer s.statsMu.Unlock()
	if old := s.statsTimer[slug]; old != nil {
		old.Stop()
	}
	var timer *time.Timer
	timer = time.AfterFunc(2*time.Second, func() {
		s.updateNovelStats(slug)
		s.statsMu.Lock()
		if s.statsTimer[slug] == timer {
			delete(s.statsTimer, slug)
		}
		s.statsMu.Unlock()
	})
	s.statsTimer[slug] = timer
}

func (s *Store) updateNovelStats(slug string) {
	slug = pathSafeSlug(slug)
	chapters, err := s.ListChapters(slug)
	if err != nil {
		log.Printf("update stats %s: list chapters: %v", slug, err)
		return
	}

	transCount := 0
	for _, chapter := range chapters {
		if chapter.HasTranslated {
			transCount++
		}
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	novelPath := filepath.Join(s.DataDir, slug, "novel.json")
	data, err := os.ReadFile(novelPath)
	if err != nil {
		log.Printf("update stats %s: read novel: %v", slug, err)
		return
	}
	var n model.Novel
	if err := json.Unmarshal(data, &n); err != nil {
		log.Printf("update stats %s: parse novel: %v", slug, err)
		return
	}
	if n.TotalChapters == len(chapters) && n.TranslatedChapters == transCount {
		return
	}

	n.TotalChapters = len(chapters)
	n.TranslatedChapters = transCount
	n.UpdatedAt = time.Now()
	updatedData, err := json.MarshalIndent(n, "", "  ")
	if err != nil {
		log.Printf("update stats %s: marshal: %v", slug, err)
		return
	}
	if err := writeFileAtomic(novelPath, updatedData); err != nil {
		log.Printf("update stats %s: write: %v", slug, err)
	}
}
