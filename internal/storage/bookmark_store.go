package storage

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"

	"novelclaw/internal/model"
)

// GetBookmark returns the user bookmark for a novel
func (s *Store) GetBookmark(slug string) (*model.Bookmark, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	slug = pathSafeSlug(slug)
	bookmarkPath := filepath.Join(s.DataDir, slug, "bookmark.json")
	data, err := os.ReadFile(bookmarkPath)
	if err != nil {
		return &model.Bookmark{NovelSlug: slug, ChapterNo: 1, ScrollPercentage: 0}, nil
	}

	var b model.Bookmark
	if err := json.Unmarshal(data, &b); err != nil {
		return &model.Bookmark{NovelSlug: slug, ChapterNo: 1, ScrollPercentage: 0}, nil
	}
	return &b, nil
}

// SaveBookmark saves the user bookmark for a novel
func (s *Store) SaveBookmark(b *model.Bookmark) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	b.UpdatedAt = time.Now()
	b.NovelSlug = pathSafeSlug(b.NovelSlug)
	bookmarkDir := filepath.Join(s.DataDir, b.NovelSlug)
	if err := os.MkdirAll(bookmarkDir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(b, "", "  ")
	if err != nil {
		return err
	}

	return writeFileAtomic(filepath.Join(bookmarkDir, "bookmark.json"), data)
}
