package storage

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"novelclaw/internal/model"
)

// Store handles all file operations for novels, chapters, bookmarks, and glossaries
type Store struct {
	DataDir string
	mu      sync.RWMutex
}

// NewStore creates a new storage manager
func NewStore(dataDir string) *Store {
	_ = os.MkdirAll(dataDir, 0755)
	return &Store{DataDir: dataDir}
}

// ListNovels returns all novels available in DataDir
func (s *Store) ListNovels() ([]model.Novel, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	entries, err := os.ReadDir(s.DataDir)
	if err != nil {
		return nil, err
	}

	var novels []model.Novel
	for _, entry := range entries {
		if !entry.IsDir() || strings.HasPrefix(entry.Name(), ".") {
			continue
		}
		slug := entry.Name()
		novelPath := filepath.Join(s.DataDir, slug, "novel.json")
		data, err := os.ReadFile(novelPath)
		if err != nil {
			// If novel.json missing, try inferring from directory name
			novels = append(novels, model.Novel{
				Slug:       slug,
				Title:      slug,
				SourceLang: "cn",
				TargetLang: "th",
				UpdatedAt:  time.Now(),
			})
			continue
		}

		var n model.Novel
		if err := json.Unmarshal(data, &n); err == nil {
			if n.Slug == "" {
				n.Slug = slug
			}
			novels = append(novels, n)
		}
	}

	// Sort by updatedAt descending
	sort.Slice(novels, func(i, j int) bool {
		return novels[i].UpdatedAt.After(novels[j].UpdatedAt)
	})

	return novels, nil
}

// GetNovel returns a single novel by its slug
func (s *Store) GetNovel(slug string) (*model.Novel, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	slug = pathSafeSlug(slug)
	novelPath := filepath.Join(s.DataDir, slug, "novel.json")
	data, err := os.ReadFile(novelPath)
	if err != nil {
		return nil, fmt.Errorf("novel not found: %s", slug)
	}

	var n model.Novel
	if err := json.Unmarshal(data, &n); err != nil {
		return nil, err
	}
	if n.Slug == "" {
		n.Slug = slug
	}
	return &n, nil
}

// SaveNovel saves or updates novel metadata
func (s *Store) SaveNovel(n *model.Novel) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if n.Slug == "" {
		n.Slug = sanitizeSlug(n.Title)
	}
	n.Slug = pathSafeSlug(n.Slug)
	n.UpdatedAt = time.Now()

	novelDir := filepath.Join(s.DataDir, n.Slug)
	if err := os.MkdirAll(novelDir, 0755); err != nil {
		return err
	}

	_ = os.MkdirAll(filepath.Join(novelDir, "chapters"), 0755)
	_ = os.MkdirAll(filepath.Join(novelDir, "glossary"), 0755)

	data, err := json.MarshalIndent(n, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(novelDir, "novel.json"), data, 0644)
}

// ListChapters returns summary metadata for all chapters in a novel
func (s *Store) ListChapters(slug string) ([]model.ChapterMeta, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	slug = pathSafeSlug(slug)
	chaptersDir := filepath.Join(s.DataDir, slug, "chapters")
	entries, err := os.ReadDir(chaptersDir)
	if err != nil {
		return []model.ChapterMeta{}, nil
	}

	chapterMap := make(map[int]*model.ChapterMeta)

	for _, entry := range entries {
		name := entry.Name()
		if !strings.HasSuffix(name, ".json") {
			continue
		}

		parts := strings.Split(strings.TrimSuffix(name, ".json"), ".")
		if len(parts) == 0 {
			continue
		}

		chNum, err := strconv.Atoi(parts[0])
		if err != nil {
			continue
		}

		meta, exists := chapterMap[chNum]
		if !exists {
			meta = &model.ChapterMeta{
				ChapterNo: chNum,
			}
			chapterMap[chNum] = meta
		}

		info, _ := entry.Info()
		if info != nil && info.ModTime().After(meta.UpdatedAt) {
			meta.UpdatedAt = info.ModTime()
		}

		isSource := strings.Contains(name, ".cn.") || strings.Contains(name, ".source.")
		isTranslated := strings.Contains(name, ".th.") || strings.Contains(name, ".translated.")

		if isSource {
			meta.HasSource = true
		}
		if isTranslated {
			meta.HasTranslated = true
		}
	}

	var result []model.ChapterMeta
	for _, meta := range chapterMap {
		result = append(result, *meta)
	}

	sort.Slice(result, func(i, j int) bool {
		return result[i].ChapterNo < result[j].ChapterNo
	})

	return result, nil
}

// GetChapter returns the content of a specific chapter
func (s *Store) GetChapter(slug string, chapterNo int) (*model.ChapterContent, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	slug = pathSafeSlug(slug)
	numStr := fmt.Sprintf("%04d", chapterNo)
	chaptersDir := filepath.Join(s.DataDir, slug, "chapters")

	content := &model.ChapterContent{
		NovelSlug: slug,
		ChapterNo: chapterNo,
		Status:    "source",
	}

	// 1. Try reading source chapter
	sourceFile := filepath.Join(chaptersDir, numStr+".cn.json")
	if _, err := os.Stat(sourceFile); os.IsNotExist(err) {
		sourceFile = filepath.Join(chaptersDir, numStr+".source.json")
	}

	if data, err := os.ReadFile(sourceFile); err == nil {
		parseChapterJSON(data, content, true)
	}

	// 2. Try reading translated chapter
	thFile := filepath.Join(chaptersDir, numStr+".th.json")
	if _, err := os.Stat(thFile); os.IsNotExist(err) {
		thFile = filepath.Join(chaptersDir, numStr+".translated.json")
	}

	if data, err := os.ReadFile(thFile); err == nil {
		parseChapterJSON(data, content, false)
		content.Status = "translated"
	}

	if len(content.SourceText) == 0 && len(content.TranslatedText) == 0 {
		return nil, fmt.Errorf("chapter %d not found in novel %s", chapterNo, slug)
	}

	return content, nil
}

// SaveChapter saves source or translated chapter content
func (s *Store) SaveChapter(slug string, chapterNo int, sourceTitle, transTitle string, sourceParagraphs, transParagraphs []string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	slug = pathSafeSlug(slug)
	numStr := fmt.Sprintf("%04d", chapterNo)
	chaptersDir := filepath.Join(s.DataDir, slug, "chapters")
	_ = os.MkdirAll(chaptersDir, 0755)

	// Save source if provided
	if len(sourceParagraphs) > 0 {
		srcData := map[string]interface{}{
			"novelId":    slug,
			"chapterNo":  chapterNo,
			"sourceLang": "cn",
			"targetLang": "th",
			"title": map[string]string{
				"source": sourceTitle,
			},
			"status":     "source",
			"paragraphs": sourceParagraphs,
			"updatedAt":  time.Now().Format(time.RFC3339),
		}
		data, _ := json.MarshalIndent(srcData, "", "  ")
		_ = os.WriteFile(filepath.Join(chaptersDir, numStr+".cn.json"), data, 0644)
	}

	// Save translated if provided
	if len(transParagraphs) > 0 {
		thData := map[string]interface{}{
			"novelId":    slug,
			"chapterNo":  chapterNo,
			"sourceLang": "cn",
			"targetLang": "th",
			"title": map[string]string{
				"source":     sourceTitle,
				"translated": transTitle,
			},
			"status":     "translated",
			"paragraphs": transParagraphs,
			"updatedAt":  time.Now().Format(time.RFC3339),
		}
		data, _ := json.MarshalIndent(thData, "", "  ")
		_ = os.WriteFile(filepath.Join(chaptersDir, numStr+".th.json"), data, 0644)
	}

	// Update novel chapter count
	go s.updateNovelStats(slug)

	return nil
}

// GetGlossary returns glossary terms for a novel
func (s *Store) GetGlossary(slug string) (*model.NovelGlossary, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	slug = pathSafeSlug(slug)
	glossaryPath := filepath.Join(s.DataDir, slug, "glossary", "glossary.json")
	if _, err := os.Stat(glossaryPath); os.IsNotExist(err) {
		glossaryPath = filepath.Join(s.DataDir, slug, "glossary.json")
	}

	g := &model.NovelGlossary{
		NovelSlug: slug,
		Terms:     []model.GlossaryItem{},
	}

	data, err := os.ReadFile(glossaryPath)
	if err != nil {
		return g, nil
	}

	// Supports both array of items and map/struct
	var items []model.GlossaryItem
	if err := json.Unmarshal(data, &items); err == nil {
		g.Terms = items
		return g, nil
	}

	var rawMap map[string]interface{}
	if err := json.Unmarshal(data, &rawMap); err == nil {
		if termsRaw, ok := rawMap["terms"]; ok {
			termsData, _ := json.Marshal(termsRaw)
			_ = json.Unmarshal(termsData, &g.Terms)
		}
	}

	return g, nil
}

// SaveGlossary saves glossary terms for a novel
func (s *Store) SaveGlossary(g *model.NovelGlossary) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	g.NovelSlug = pathSafeSlug(g.NovelSlug)
	glossaryDir := filepath.Join(s.DataDir, g.NovelSlug, "glossary")
	_ = os.MkdirAll(glossaryDir, 0755)

	data, err := json.MarshalIndent(g.Terms, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(glossaryDir, "glossary.json"), data, 0644)
}

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
	_ = os.MkdirAll(bookmarkDir, 0755)

	data, err := json.MarshalIndent(b, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(filepath.Join(bookmarkDir, "bookmark.json"), data, 0644)
}

func (s *Store) updateNovelStats(slug string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	slug = pathSafeSlug(slug)
	novelPath := filepath.Join(s.DataDir, slug, "novel.json")
	data, err := os.ReadFile(novelPath)
	if err != nil {
		return
	}

	var n model.Novel
	if err := json.Unmarshal(data, &n); err != nil {
		return
	}

	chaptersDir := filepath.Join(s.DataDir, slug, "chapters")
	entries, _ := os.ReadDir(chaptersDir)

	srcCount := 0
	transCount := 0
	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}
		if strings.Contains(entry.Name(), ".cn.") || strings.Contains(entry.Name(), ".source.") {
			srcCount++
		}
		if strings.Contains(entry.Name(), ".th.") || strings.Contains(entry.Name(), ".translated.") {
			transCount++
		}
	}

	if n.TotalChapters == srcCount && n.TranslatedChapters == transCount {
		return // No change, avoid unnecessary disk write
	}

	n.TotalChapters = srcCount
	n.TranslatedChapters = transCount
	n.UpdatedAt = time.Now()

	updatedData, _ := json.MarshalIndent(n, "", "  ")
	_ = os.WriteFile(novelPath, updatedData, 0644)
}

// Helper: parse flexible chapter JSON (handles raw strings or {"text": "..."} objects, and string/struct titles)
func parseChapterJSON(data []byte, content *model.ChapterContent, isSource bool) {
	var raw struct {
		Title      json.RawMessage   `json:"title"`
		Paragraphs []json.RawMessage `json:"paragraphs"`
	}

	if err := json.Unmarshal(data, &raw); err != nil {
		return
	}

	// Try title as struct
	var titleObj struct {
		Source     string `json:"source"`
		Translated string `json:"translated"`
	}
	if err := json.Unmarshal(raw.Title, &titleObj); err == nil && (titleObj.Source != "" || titleObj.Translated != "") {
		if isSource {
			if titleObj.Source != "" {
				content.SourceTitle = titleObj.Source
			}
		} else {
			if titleObj.Translated != "" {
				content.TranslatedTitle = titleObj.Translated
			}
			if content.SourceTitle == "" && titleObj.Source != "" {
				content.SourceTitle = titleObj.Source
			}
		}
	} else {
		// Fallback: title as simple string
		var titleStr string
		if err := json.Unmarshal(raw.Title, &titleStr); err == nil && titleStr != "" {
			if isSource {
				content.SourceTitle = titleStr
			} else {
				content.TranslatedTitle = titleStr
			}
		}
	}

	var lines []string
	for _, pRaw := range raw.Paragraphs {
		var s string
		if err := json.Unmarshal(pRaw, &s); err == nil {
			s = strings.TrimSpace(s)
			if s != "" {
				lines = append(lines, s)
			}
			continue
		}

		var obj struct {
			Text string `json:"text"`
		}
		if err := json.Unmarshal(pRaw, &obj); err == nil {
			txt := strings.TrimSpace(obj.Text)
			if txt != "" {
				lines = append(lines, txt)
			}
		}
	}

	if isSource {
		content.SourceText = lines
	} else {
		content.TranslatedText = lines
	}
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

// pathSafeSlug strips everything outside [A-Za-z0-9_-] so a slug can never
// contain path separators or ".." and therefore cannot escape DataDir.
// Unlike sanitizeSlug it does not lowercase, so existing on-disk slugs keep
// working for reads.
func pathSafeSlug(slug string) string {
	var b strings.Builder
	for _, r := range slug {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '-' || r == '_' {
			b.WriteRune(r)
		}
	}
	if b.Len() == 0 {
		return "_invalid_"
	}
	return b.String()
}
