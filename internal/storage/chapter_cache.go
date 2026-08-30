package storage

import "novelclaw/internal/model"

func cloneChapterMeta(items []model.ChapterMeta) []model.ChapterMeta {
	if len(items) == 0 {
		return []model.ChapterMeta{}
	}
	return append([]model.ChapterMeta(nil), items...)
}

func (s *Store) getChapterCache(slug string) ([]model.ChapterMeta, bool) {
	s.chapterCacheMu.RLock()
	items, ok := s.chapterCache[slug]
	if ok {
		items = cloneChapterMeta(items)
	}
	s.chapterCacheMu.RUnlock()
	return items, ok
}

func (s *Store) setChapterCache(slug string, items []model.ChapterMeta) {
	s.chapterCacheMu.Lock()
	s.chapterCache[slug] = cloneChapterMeta(items)
	s.chapterCacheMu.Unlock()
}

func (s *Store) invalidateChapterCache(slug string) {
	s.chapterCacheMu.Lock()
	delete(s.chapterCache, slug)
	s.chapterCacheMu.Unlock()
}
