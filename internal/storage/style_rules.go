package storage

import (
	"os"
	"path/filepath"
	"strings"

	"novelclaw/internal/model"
)

// GetStyleRules returns the novel's style_rules.yml rendered as prompt-ready
// text. Returns "" when the file is absent or empty.
func (s *Store) GetStyleRules(slug string) (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	slug = pathSafeSlug(slug)
	path := filepath.Join(s.DataDir, slug, "style_rules.yml")
	data, err := os.ReadFile(path)
	if err != nil {
		return "", nil
	}
	return renderStyleRules(string(data)), nil
}

// renderStyleRules parses the flat YAML layout used by style_rules.yml:
// section headers ("name:") followed by "- text:" items, single-quoted
// scalars with 4-space continuation lines. Stdlib-only on purpose.
// ponytail: not a general YAML parser; upgrade to gopkg.in/yaml.v3 if the
// format grows nested structures.
func renderStyleRules(data string) string {
	var out []string
	var item strings.Builder
	open := false // inside an unclosed single-quoted scalar

	flush := func() {
		if item.Len() > 0 {
			out = append(out, "- "+strings.TrimSpace(item.String()))
			item.Reset()
		}
		open = false
	}

	for _, raw := range strings.Split(data, "\n") {
		line := strings.TrimRight(raw, "\r")
		trimmed := strings.TrimSpace(line)

		if open && strings.HasPrefix(line, "    ") {
			part := trimmed
			if strings.HasSuffix(part, "'") {
				part = strings.TrimSuffix(part, "'")
				open = false
			}
			item.WriteString(" " + part)
			continue
		}
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		if strings.HasPrefix(trimmed, "- text:") {
			flush()
			val := strings.TrimSpace(strings.TrimPrefix(trimmed, "- text:"))
			if strings.HasPrefix(val, "'") && !strings.HasSuffix(val, "'") {
				open = true
				item.WriteString(strings.TrimPrefix(val, "'"))
			} else {
				item.WriteString(stripSingleQuotes(val))
			}
			continue
		}
		if strings.HasSuffix(trimmed, ":") {
			flush()
			out = append(out, "["+strings.TrimSuffix(trimmed, ":")+"]")
		}
	}
	flush()
	return strings.Join(out, "\n")
}

// stripSingleQuotes unwraps a single-quoted YAML scalar (” -> ').
func stripSingleQuotes(v string) string {
	if len(v) >= 2 && strings.HasPrefix(v, "'") && strings.HasSuffix(v, "'") {
		return strings.ReplaceAll(v[1:len(v)-1], "''", "'")
	}
	return v
}

// mergeGlossaryYAML appends terms from glossary/glossary.yml (the bulk term
// base generated from locked/reference/auto.md) to the curated glossary.json
// terms. glossary.json wins on conflicts.
func mergeGlossaryYAML(dataDir, slug string, terms []model.GlossaryItem) []model.GlossaryItem {
	ymlPath := filepath.Join(dataDir, slug, "glossary", "glossary.yml")
	if _, err := os.Stat(ymlPath); os.IsNotExist(err) {
		ymlPath = filepath.Join(dataDir, slug, "glossary.yml")
	}
	data, err := os.ReadFile(ymlPath)
	if err != nil {
		return terms
	}
	seen := make(map[string]bool, len(terms))
	for _, t := range terms {
		seen[t.Term] = true
	}
	for _, t := range parseGlossaryYAML(string(data)) {
		if t.Term != "" && !seen[t.Term] {
			terms = append(terms, t)
			seen[t.Term] = true
		}
	}
	return terms
}

// parseGlossaryYAML parses the flat "terms:" list layout produced by
// tools/build_yaml.py. All values are single-line scalars in that format.
func parseGlossaryYAML(data string) []model.GlossaryItem {
	var items []model.GlossaryItem
	var cur *model.GlossaryItem

	for _, raw := range strings.Split(data, "\n") {
		trimmed := strings.TrimSpace(strings.TrimRight(raw, "\r"))
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		if strings.HasPrefix(trimmed, "- source:") {
			if cur != nil && cur.Term != "" && cur.Target != "" {
				items = append(items, *cur)
			}
			cur = &model.GlossaryItem{
				Term: stripSingleQuotes(strings.TrimSpace(strings.TrimPrefix(trimmed, "- source:"))),
			}
			continue
		}
		if cur == nil {
			continue
		}
		key, val, ok := strings.Cut(trimmed, ":")
		if !ok {
			continue
		}
		val = stripSingleQuotes(strings.TrimSpace(val))
		switch strings.TrimSpace(key) {
		case "thai":
			cur.Target = val
		case "category":
			cur.Category = val
		case "notes":
			cur.Notes = val
		case "explanation":
			if val != "" {
				if cur.Notes != "" {
					cur.Notes += "; " + val
				} else {
					cur.Notes = val
				}
			}
		}
	}
	if cur != nil && cur.Term != "" && cur.Target != "" {
		items = append(items, *cur)
	}
	return items
}
