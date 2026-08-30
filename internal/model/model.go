package model

import "time"

// Novel represents novel metadata
type Novel struct {
	Slug               string            `json:"slug"`
	Title              string            `json:"title"`
	TranslatedTitle    string            `json:"translatedTitle,omitempty"`
	Author             string            `json:"author,omitempty"`
	SourceLang         string            `json:"sourceLang"`
	TargetLang         string            `json:"targetLang"`
	Genre              string            `json:"genre,omitempty"` // "apocalypse", "xianxia", "system", "urban", "fantasy"
	Description        string            `json:"description,omitempty"`
	CoverURL           string            `json:"coverUrl,omitempty"`
	TotalChapters      int               `json:"totalChapters"`
	TranslatedChapters int               `json:"translatedChapters"`
	SourceURLs         map[string]string `json:"sourceUrls,omitempty"`
	UpdatedAt          time.Time         `json:"updatedAt"`
}

// ChapterMeta represents lightweight metadata for chapter listing
type ChapterMeta struct {
	ChapterNo       int       `json:"chapterNo"`
	TitleSource     string    `json:"titleSource"`
	TitleTranslated string    `json:"titleTranslated,omitempty"`
	HasSource       bool      `json:"hasSource"`
	HasTranslated   bool      `json:"hasTranslated"`
	UpdatedAt       time.Time `json:"updatedAt"`
}

// ChapterContent represents full content of a chapter
type ChapterContent struct {
	NovelSlug       string    `json:"novelSlug"`
	ChapterNo       int       `json:"chapterNo"`
	SourceTitle     string    `json:"sourceTitle"`
	TranslatedTitle string    `json:"translatedTitle,omitempty"`
	SourceLang      string    `json:"sourceLang"`
	TargetLang      string    `json:"targetLang"`
	SourceText      []string  `json:"sourceText"`
	TranslatedText  []string  `json:"translatedText,omitempty"`
	Status          string    `json:"status"` // "source", "translated", "in_progress"
	UpdatedAt       time.Time `json:"updatedAt"`
}

// GlossaryItem represents a single terminology or character mapping
type GlossaryItem struct {
	Term     string `json:"term"`     // Original text (e.g. 曹星)
	Target   string `json:"target"`   // Thai translation (e.g. เฉาซิง)
	Category string `json:"category"` // "character", "location", "skill", "item", "custom"
	Notes    string `json:"notes,omitempty"`
}

// NovelGlossary contains the glossary terms for a specific novel
type NovelGlossary struct {
	NovelSlug string         `json:"novelSlug"`
	Terms     []GlossaryItem `json:"terms"`
}

// CharacterMemory stores stable identity/pronoun facts across long novels.
type CharacterMemory struct {
	SourceName string `json:"sourceName,omitempty"`
	ThaiName   string `json:"thaiName"`
	Role       string `json:"role,omitempty"`
	Gender     string `json:"gender,omitempty"`
	Pronouns   string `json:"pronouns,omitempty"`
	Notes      string `json:"notes,omitempty"`
}

type NovelMemory struct {
	NovelSlug    string            `json:"novelSlug"`
	StorySummary string            `json:"storySummary,omitempty"`
	Characters   []CharacterMemory `json:"characters,omitempty"`
	Facts        []string          `json:"facts,omitempty"`
	UpdatedAt    time.Time         `json:"updatedAt"`
}

type TranslationQualityIssue struct {
	Code     string `json:"code"`
	Severity string `json:"severity"`
	Message  string `json:"message"`
}

type TranslationQualityReport struct {
	NovelSlug            string                    `json:"novelSlug"`
	ChapterNo            int                       `json:"chapterNo"`
	Score                int                       `json:"score"`
	SourceParagraphs     int                       `json:"sourceParagraphs"`
	TranslatedParagraphs int                       `json:"translatedParagraphs"`
	Issues               []TranslationQualityIssue `json:"issues"`
	CheckedAt            time.Time                 `json:"checkedAt"`
}

// Bookmark stores the user's reading position
type Bookmark struct {
	NovelSlug        string    `json:"novelSlug"`
	ChapterNo        int       `json:"chapterNo"`
	ScrollPercentage float64   `json:"scrollPercentage"`
	UpdatedAt        time.Time `json:"updatedAt"`
}

// ImportRequest represents a request to import chapters
type ImportRequest struct {
	URL          string `json:"url,omitempty"`
	NovelSlug    string `json:"novelSlug,omitempty"`
	NovelTitle   string `json:"novelTitle,omitempty"`
	Title        string `json:"title,omitempty"`
	Author       string `json:"author,omitempty"`
	Genre        string `json:"genre,omitempty"`
	SourceLang   string `json:"sourceLang,omitempty"`
	StartChapter int    `json:"startChapter,omitempty"`
	EndChapter   int    `json:"endChapter,omitempty"`
	RawContent   string `json:"rawContent,omitempty"` // For manual paste
}

// TranslateRequest represents a request to translate chapters
type TranslateRequest struct {
	NovelSlug      string   `json:"novelSlug"`
	Provider       string   `json:"provider,omitempty"`
	StartChapter   int      `json:"startChapter"`
	EndChapter     int      `json:"endChapter"`
	Model          string   `json:"model,omitempty"`
	FallbackModels []string `json:"fallbackModels,omitempty"` // tried in order if Model fails
	Genre          string   `json:"genre,omitempty"`
	Temperature    float64  `json:"temperature,omitempty"`
	Force          bool     `json:"force,omitempty"` // Re-translate even if already translated
}

// DiscoverGlossaryRequest represents a request to discover glossary terms
type DiscoverGlossaryRequest struct {
	NovelSlug    string `json:"novelSlug"`
	StartChapter int    `json:"startChapter"`
	EndChapter   int    `json:"endChapter"`
	Model        string `json:"model,omitempty"`
}

// TranslationProgress reports progress during batch translation
type TranslationProgress struct {
	JobID          string `json:"jobId"`
	NovelSlug      string `json:"novelSlug"`
	CurrentChapter int    `json:"currentChapter"`
	TotalChapters  int    `json:"totalChapters"`
	Status         string `json:"status"` // "running", "completed", "error"
	Message        string `json:"message"`
	Percentage     int    `json:"percentage"`
	ErrorDetails   string `json:"errorDetails,omitempty"`
}
