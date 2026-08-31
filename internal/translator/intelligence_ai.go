package translator

import (
	"encoding/json"
	"fmt"
	"strings"

	"novelclaw/internal/model"
)

// BuildMemoryExtractionPrompts asks an LLM for a compact continuity snapshot.
// The caller previews/merges the result; this function never persists memory.
func BuildMemoryExtractionPrompts(existing *model.NovelMemory, chapterContext string) (string, string) {
	existingJSON, _ := json.Marshal(existing)
	system := `You maintain long-term memory for a Thai novel translator.
Return ONLY valid JSON with this shape:
{"storySummary":"...","characters":[{"sourceName":"","thaiName":"","role":"","gender":"","pronouns":"","notes":""}],"facts":["..."]}
Keep only stable facts supported by the supplied chapters. Do not invent details.
Keep names and pronouns consistent. The summary must be compact and useful for future translation.`
	user := fmt.Sprintf("Existing curated memory (preserve its intent):\n%s\n\nRecent chapter context:\n%s", string(existingJSON), chapterContext)
	return system, user
}
func ParseNovelMemoryCandidate(raw string) (*model.NovelMemory, error) {
	payload, err := extractJSONObject(raw)
	if err != nil {
		return nil, fmt.Errorf("invalid memory response: %w", err)
	}
	var memory model.NovelMemory
	if err := json.Unmarshal([]byte(payload), &memory); err != nil {
		return nil, fmt.Errorf("invalid memory JSON: %w", err)
	}
	memory.StorySummary = strings.TrimSpace(memory.StorySummary)
	memory.Facts = compactUniqueStrings(memory.Facts, 200)
	cleanCharacters := make([]model.CharacterMemory, 0, len(memory.Characters))
	for _, ch := range memory.Characters {
		ch = normalizeCharacterMemory(ch)
		if ch.SourceName == "" && ch.ThaiName == "" {
			continue
		}
		cleanCharacters = append(cleanCharacters, ch)
		if len(cleanCharacters) >= 200 {
			break
		}
	}
	memory.Characters = cleanCharacters
	return &memory, nil
}

func normalizeCharacterMemory(ch model.CharacterMemory) model.CharacterMemory {
	ch.SourceName = strings.TrimSpace(ch.SourceName)
	ch.ThaiName = strings.TrimSpace(ch.ThaiName)
	ch.Role = strings.TrimSpace(ch.Role)
	ch.Gender = strings.TrimSpace(ch.Gender)
	ch.Pronouns = strings.TrimSpace(ch.Pronouns)
	ch.Notes = strings.TrimSpace(ch.Notes)
	return ch
}

// MergeNovelMemory merges an AI candidate into stored memory. When fresh is
// true the candidate reflects chapters translated AFTER the stored memory was
// written, so its non-empty fields replace stale ones (identity fields like
// ThaiName are still fill-only — renames stay a human decision). When fresh
// is false only blanks are filled: manual edits always win.
func MergeNovelMemory(existing, candidate *model.NovelMemory, fresh bool) *model.NovelMemory {
	merged := &model.NovelMemory{Characters: []model.CharacterMemory{}, Facts: []string{}}
	if existing != nil {
		*merged = *existing
		merged.Characters = append([]model.CharacterMemory(nil), existing.Characters...)
		merged.Facts = append([]string(nil), existing.Facts...)
	}
	if candidate == nil {
		return merged
	}
	if strings.TrimSpace(candidate.StorySummary) != "" {
		merged.StorySummary = strings.TrimSpace(candidate.StorySummary)
	}
	index := make(map[string]int, len(merged.Characters)*2)
	for i, ch := range merged.Characters {
		for _, key := range characterKeys(ch) {
			index[key] = i
		}
	}
	for _, incoming := range candidate.Characters {
		incoming = normalizeCharacterMemory(incoming)
		match := -1
		for _, key := range characterKeys(incoming) {
			if i, ok := index[key]; ok {
				match = i
				break
			}
		}
		if match >= 0 {
			if fresh {
				merged.Characters[match] = refreshCharacter(merged.Characters[match], incoming)
			} else {
				merged.Characters[match] = fillCharacterBlanks(merged.Characters[match], incoming)
			}
			continue
		}
		if incoming.SourceName == "" && incoming.ThaiName == "" {
			continue
		}
		merged.Characters = append(merged.Characters, incoming)
		for _, key := range characterKeys(incoming) {
			index[key] = len(merged.Characters) - 1
		}
	}
	merged.Facts = compactUniqueStrings(append(merged.Facts, candidate.Facts...), 200)
	return merged
}

// refreshCharacter updates progression fields with fresher observations
// (roles, levels, locations evolve over a long novel) while identity fields —
// names, gender, pronouns — stay anchored to existing curation.
func refreshCharacter(curated, incoming model.CharacterMemory) model.CharacterMemory {
	if curated.ThaiName == "" {
		curated.ThaiName = incoming.ThaiName
	}
	if curated.SourceName == "" {
		curated.SourceName = incoming.SourceName
	}
	if incoming.Role != "" {
		curated.Role = incoming.Role
	}
	if incoming.Notes != "" {
		curated.Notes = incoming.Notes
	}
	if curated.Gender == "" {
		curated.Gender = incoming.Gender
	}
	if curated.Pronouns == "" {
		curated.Pronouns = incoming.Pronouns
	}
	return curated
}
func characterKeys(ch model.CharacterMemory) []string {
	keys := []string{}
	if value := strings.ToLower(strings.TrimSpace(ch.SourceName)); value != "" {
		keys = append(keys, "s:"+value)
	}
	if value := strings.ToLower(strings.TrimSpace(ch.ThaiName)); value != "" {
		keys = append(keys, "t:"+value)
	}
	return keys
}

func fillCharacterBlanks(curated, incoming model.CharacterMemory) model.CharacterMemory {
	curated = normalizeCharacterMemory(curated)
	incoming = normalizeCharacterMemory(incoming)
	if curated.SourceName == "" {
		curated.SourceName = incoming.SourceName
	}
	if curated.ThaiName == "" {
		curated.ThaiName = incoming.ThaiName
	}
	if curated.Role == "" {
		curated.Role = incoming.Role
	}
	if curated.Gender == "" {
		curated.Gender = incoming.Gender
	}
	if curated.Pronouns == "" {
		curated.Pronouns = incoming.Pronouns
	}
	if curated.Notes == "" {
		curated.Notes = incoming.Notes
	}
	return curated
}

func compactUniqueStrings(values []string, max int) []string {
	out := make([]string, 0, len(values))
	seen := map[string]bool{}
	for _, value := range values {
		value = strings.TrimSpace(value)
		key := strings.ToLower(value)
		if value == "" || seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, value)
		if len(out) >= max {
			break
		}
	}
	return out
}
func BuildQARepairPrompts(chapter *model.ChapterContent, report model.TranslationQualityReport, glossary *model.NovelGlossary, memoryContext, styleRules string) (string, string) {
	contextJSON, _ := json.Marshal(map[string]interface{}{
		"sourceTitle":        chapter.SourceTitle,
		"translatedTitle":    chapter.TranslatedTitle,
		"sourceParagraphs":   chapter.SourceText,
		"currentTranslation": chapter.TranslatedText,
		"qaIssues":           report.Issues,
		"glossary":           glossary,
		"memory":             memoryContext,
		"styleRules":         styleRules,
	})
	system := `You repair an existing Thai novel translation.
Return ONLY valid JSON: {"title":"...","paragraphs":["..."]}.
Keep exactly the same paragraph count as sourceParagraphs.
Preserve all numbers, facts, names, and paragraph order. Follow the glossary exactly.
Fix only translation/continuity/terminology problems. Do not summarize or add content.
The result must be natural Thai and must not contain Chinese characters unless a glossary target intentionally contains them.`
	return system, string(contextJSON)
}

func ParseQARepairCandidate(raw string, expectedParagraphs int) (string, []string, error) {
	payload, err := extractJSONObject(raw)
	if err != nil {
		return "", nil, fmt.Errorf("invalid repair response: %w", err)
	}
	var candidate struct {
		Title      string   `json:"title"`
		Paragraphs []string `json:"paragraphs"`
	}
	if err := json.Unmarshal([]byte(payload), &candidate); err != nil {
		return "", nil, fmt.Errorf("invalid repair JSON: %w", err)
	}
	candidate.Title = strings.TrimSpace(candidate.Title)
	for i := range candidate.Paragraphs {
		candidate.Paragraphs[i] = strings.TrimSpace(candidate.Paragraphs[i])
	}
	if len(candidate.Paragraphs) != expectedParagraphs {
		return "", nil, fmt.Errorf("repair paragraph count mismatch: got %d want %d", len(candidate.Paragraphs), expectedParagraphs)
	}
	for i, paragraph := range candidate.Paragraphs {
		if paragraph == "" {
			return "", nil, fmt.Errorf("repair returned empty paragraph %d", i+1)
		}
	}
	return candidate.Title, candidate.Paragraphs, nil
}
func extractJSONObject(raw string) (string, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "", fmt.Errorf("empty response")
	}
	if strings.HasPrefix(raw, "```") {
		lines := strings.Split(raw, "\n")
		if len(lines) >= 3 {
			raw = strings.Join(lines[1:len(lines)-1], "\n")
			raw = strings.TrimSpace(raw)
			if strings.HasPrefix(strings.ToLower(raw), "json\n") {
				raw = strings.TrimSpace(raw[5:])
			}
		}
	}
	start := strings.Index(raw, "{")
	end := strings.LastIndex(raw, "}")
	if start < 0 || end < start {
		return "", fmt.Errorf("JSON object not found")
	}
	return raw[start : end+1], nil
}
