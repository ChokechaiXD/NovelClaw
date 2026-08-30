package translator

import (
	"fmt"
	"strings"

	"novelclaw/internal/model"
)

// BuildMemoryContext renders compact long-term memory for prompt injection.
func BuildMemoryContext(memory *model.NovelMemory, glossary *model.NovelGlossary) string {
	var b strings.Builder
	if memory != nil && strings.TrimSpace(memory.StorySummary) != "" {
		b.WriteString("Long-term story summary: ")
		b.WriteString(limitRunes(strings.TrimSpace(memory.StorySummary), 2500))
		b.WriteString("\n")
	}
	seen := map[string]bool{}
	count := 0
	if memory != nil {
		for _, ch := range memory.Characters {
			if ch.ThaiName == "" || count >= 30 {
				continue
			}
			b.WriteString(renderCharacterMemory(ch))
			seen[ch.SourceName] = true
			seen[ch.ThaiName] = true
			count++
		}
		for i, fact := range memory.Facts {
			if i >= 20 {
				break
			}
			fact = strings.TrimSpace(fact)
			if fact != "" {
				b.WriteString("Story fact: " + limitRunes(fact, 350) + "\n")
			}
		}
	}
	if glossary != nil {
		for _, item := range glossary.Terms {
			if count >= 30 || item.Category != "character" || item.Target == "" || seen[item.Term] || seen[item.Target] {
				continue
			}
			ch := model.CharacterMemory{SourceName: item.Term, ThaiName: item.Target, Notes: item.Notes}
			b.WriteString(renderCharacterMemory(ch))
			count++
		}
	}
	return strings.TrimSpace(b.String())
}

func renderCharacterMemory(ch model.CharacterMemory) string {
	name := ch.ThaiName
	if ch.SourceName != "" {
		name = fmt.Sprintf("%s (%s)", ch.ThaiName, ch.SourceName)
	}
	parts := []string{name}
	if ch.Role != "" {
		parts = append(parts, "role="+ch.Role)
	}
	if ch.Gender != "" {
		parts = append(parts, "gender="+ch.Gender)
	}
	if ch.Pronouns != "" {
		parts = append(parts, "pronouns="+ch.Pronouns)
	}
	if ch.Notes != "" {
		parts = append(parts, "notes="+limitRunes(ch.Notes, 250))
	}
	return "Character: " + strings.Join(parts, " | ") + "\n"
}

func limitRunes(s string, max int) string {
	r := []rune(s)
	if len(r) <= max {
		return s
	}
	return string(r[:max]) + "..."
}

// BuildSystemPromptWithMemory preserves the legacy prompt API.
func BuildSystemPromptWithMemory(glossary *model.NovelGlossary, prevContext, genre, styleRules, memoryContext string) string {
	prompt := BuildSystemPrompt(glossary, prevContext, genre, styleRules)
	if strings.TrimSpace(memoryContext) == "" {
		return prompt
	}
	return prompt + "\n\n[LONG-TERM STORY MEMORY - preserve continuity; do not invent facts]\n" + strings.TrimSpace(memoryContext) + "\n"
}
