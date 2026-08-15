package translator

import (
	"strings"
)

// ParagraphChunk represents a subset of paragraphs for safe LLM translation
type ParagraphChunk struct {
	Index      int
	Paragraphs []string
}

// SplitParagraphsIntoChunks splits long chapters into smart manageable chunks (max 25 paragraphs or 750 chars)
func SplitParagraphsIntoChunks(paragraphs []string, maxCharsPerChunk int) []ParagraphChunk {
	if maxCharsPerChunk <= 0 || maxCharsPerChunk > 800 {
		maxCharsPerChunk = 750
	}
	maxParasPerChunk := 25

	var chunks []ParagraphChunk
	var currentChunk []string
	currentLength := 0

	for _, p := range paragraphs {
		trimmed := strings.TrimSpace(p)
		if trimmed == "" {
			continue
		}

		pLen := len([]rune(trimmed))

		if (len(currentChunk) >= maxParasPerChunk) || (currentLength > 0 && currentLength+pLen > maxCharsPerChunk) {
			chunks = append(chunks, ParagraphChunk{
				Index:      len(chunks),
				Paragraphs: currentChunk,
			})
			currentChunk = []string{}
			currentLength = 0
		}

		currentChunk = append(currentChunk, trimmed)
		currentLength += pLen
	}

	if len(currentChunk) > 0 {
		chunks = append(chunks, ParagraphChunk{
			Index:      len(chunks),
			Paragraphs: currentChunk,
		})
	}

	return chunks
}
