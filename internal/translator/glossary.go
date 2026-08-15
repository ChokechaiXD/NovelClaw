package translator

import (
	"strings"

	"novelclaw/internal/model"
)

// FilterRelevantGlossary filters glossary items that actually appear in the source paragraphs
func FilterRelevantGlossary(g *model.NovelGlossary, paragraphs []string) *model.NovelGlossary {
	if g == nil || len(g.Terms) == 0 {
		return g
	}

	fullText := strings.Join(paragraphs, " ")
	var relevant []model.GlossaryItem

	for _, item := range g.Terms {
		if strings.Contains(fullText, item.Term) {
			relevant = append(relevant, item)
		}
	}

	return &model.NovelGlossary{
		NovelSlug: g.NovelSlug,
		Terms:     relevant,
	}
}
