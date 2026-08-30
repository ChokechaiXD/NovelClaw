package translator

import (
	"sort"
	"strings"
	"unicode"
)

// SanitizationDiagnostics records quality damage that automatic cleanup had
// to repair. Unknown Hanzi are removed from persisted Thai text, but are no
// longer invisible to QA.
type SanitizationDiagnostics struct {
	HadHanzi            bool
	RemovedUnknownHanzi int
	UnknownSamples      []string
	AffectedParagraphs  []int
}

func SanitizeTextWithDiagnostics(text string, customGlossary map[string]string) (string, SanitizationDiagnostics) {
	diag := SanitizationDiagnostics{HadHanzi: HasHanzi(text)}
	if text == "" || !diag.HadHanzi {
		return text, diag
	}

	result := applyCustomGlossary(text, customGlossary)
	for _, item := range sortedBuiltinGlossary {
		if strings.Contains(result, item.term) {
			result = strings.ReplaceAll(result, item.term, item.repl)
		}
	}

	if !HasHanzi(result) {
		return result, diag
	}

	seenUnknown := map[rune]bool{}
	var b strings.Builder
	for _, r := range result {
		if !unicode.Is(unicode.Han, r) {
			b.WriteRune(r)
			continue
		}
		if trans, ok := SingleHanziFallback[r]; ok {
			b.WriteString(trans)
			continue
		}
		diag.RemovedUnknownHanzi++
		if !seenUnknown[r] && len(diag.UnknownSamples) < 8 {
			diag.UnknownSamples = append(diag.UnknownSamples, string(r))
			seenUnknown[r] = true
		}
	}
	return b.String(), diag
}

func applyCustomGlossary(text string, customGlossary map[string]string) string {
	if len(customGlossary) == 0 {
		return text
	}
	type kv struct{ k, v string }
	items := make([]kv, 0, len(customGlossary))
	for k, v := range customGlossary {
		if k != "" {
			items = append(items, kv{k: k, v: v})
		}
	}
	sort.Slice(items, func(i, j int) bool { return len(items[i].k) > len(items[j].k) })
	result := text
	for _, item := range items {
		if strings.Contains(result, item.k) {
			result = strings.ReplaceAll(result, item.k, item.v)
		}
	}
	return result
}

func SanitizeParagraphsWithDiagnostics(paragraphs []string, customGlossary map[string]string) ([]string, SanitizationDiagnostics) {
	cleaned := make([]string, 0, len(paragraphs))
	combined := SanitizationDiagnostics{}
	seenSample := map[string]bool{}
	for i, p := range paragraphs {
		text, diag := SanitizeTextWithDiagnostics(p, customGlossary)
		cleaned = append(cleaned, text)
		combined.HadHanzi = combined.HadHanzi || diag.HadHanzi
		combined.RemovedUnknownHanzi += diag.RemovedUnknownHanzi
		if diag.RemovedUnknownHanzi > 0 {
			combined.AffectedParagraphs = append(combined.AffectedParagraphs, i+1)
		}
		for _, sample := range diag.UnknownSamples {
			if !seenSample[sample] && len(combined.UnknownSamples) < 8 {
				combined.UnknownSamples = append(combined.UnknownSamples, sample)
				seenSample[sample] = true
			}
		}
	}
	return cleaned, combined
}

func MergeSanitizationDiagnostics(items ...SanitizationDiagnostics) SanitizationDiagnostics {
	var out SanitizationDiagnostics
	seenSample := map[string]bool{}
	seenParagraph := map[int]bool{}
	for _, item := range items {
		out.HadHanzi = out.HadHanzi || item.HadHanzi
		out.RemovedUnknownHanzi += item.RemovedUnknownHanzi
		for _, sample := range item.UnknownSamples {
			if !seenSample[sample] && len(out.UnknownSamples) < 8 {
				out.UnknownSamples = append(out.UnknownSamples, sample)
				seenSample[sample] = true
			}
		}
		for _, paragraph := range item.AffectedParagraphs {
			if !seenParagraph[paragraph] {
				out.AffectedParagraphs = append(out.AffectedParagraphs, paragraph)
				seenParagraph[paragraph] = true
			}
		}
	}
	return out
}
