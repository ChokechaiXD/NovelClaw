package storage

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"novelclaw/internal/model"
)

// GetGlossary returns glossary terms for a novel
func (s *Store) GetGlossary(slug string) (*model.NovelGlossary, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	slug = pathSafeSlug(slug)
	g := &model.NovelGlossary{NovelSlug: slug, Terms: []model.GlossaryItem{}}
	merge := func(terms []model.GlossaryItem) (*model.NovelGlossary, error) {
		merged, err := mergeGlossaryYAML(s.DataDir, slug, terms)
		if err != nil {
			return nil, err
		}
		g.Terms = merged
		return g, nil
	}
	glossaryPath := filepath.Join(s.DataDir, slug, "glossary", "glossary.json")
	if _, err := os.Stat(glossaryPath); os.IsNotExist(err) {
		glossaryPath = filepath.Join(s.DataDir, slug, "glossary.json")
	} else if err != nil {
		return nil, fmt.Errorf("stat glossary: %w", err)
	}

	data, err := os.ReadFile(glossaryPath)
	if err != nil {
		if os.IsNotExist(err) {
			return merge(nil)
		}
		return nil, fmt.Errorf("read glossary: %w", err)
	}

	var items []model.GlossaryItem
	if err := json.Unmarshal(data, &items); err == nil {
		return merge(items)
	}

	var wrapped struct {
		Terms []model.GlossaryItem `json:"terms"`
	}
	if err := json.Unmarshal(data, &wrapped); err != nil {
		return nil, fmt.Errorf("parse glossary JSON: %w", err)
	}
	return merge(wrapped.Terms)
}

// SaveGlossary saves glossary terms for a novel
func (s *Store) SaveGlossary(g *model.NovelGlossary) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	g.NovelSlug = pathSafeSlug(g.NovelSlug)
	glossaryDir := filepath.Join(s.DataDir, g.NovelSlug, "glossary")
	if err := os.MkdirAll(glossaryDir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(g.Terms, "", "  ")
	if err != nil {
		return err
	}
	if err := writeFileAtomic(filepath.Join(glossaryDir, "glossary.json"), data); err != nil {
		return err
	}
	s.setGlossaryCache(g.NovelSlug, g.Terms)
	return nil
}
