package translator

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
	"time"

	"novelclaw/internal/model"
)

var numberTokenRE = regexp.MustCompile(`\d+(?:[.,]\d+)?%?`)

// normalizeNumberToken strips thousands separators and percent signs so that
// "38,024", "38024" and "30%" vs "ร้อยละ 30" compare equal.
func normalizeNumberToken(tok string) string {
	tok = strings.ReplaceAll(tok, ",", "")
	return strings.TrimSuffix(tok, "%")
}

// findMissingNumbers returns source-side numbers that never appear in the
// translation. The check is one-directional on purpose: Thai prose freely
// converts Chinese numerals (六小时 → 6) and reorders game values, so extra
// numbers on the Thai side are normal, while a number vanishing from the
// translation is the real failure mode.
func findMissingNumbers(source, translated []string) []string {
	counts := make(map[string]int)
	for _, tok := range numberTokenRE.FindAllString(strings.Join(source, " "), -1) {
		counts[normalizeNumberToken(tok)]++
	}
	for _, tok := range numberTokenRE.FindAllString(strings.Join(translated, " "), -1) {
		tok = normalizeNumberToken(tok)
		if n, ok := counts[tok]; ok {
			if n <= 1 {
				delete(counts, tok)
			} else {
				counts[tok] = n - 1
			}
		}
	}
	missing := make([]string, 0, len(counts))
	for tok, n := range counts {
		for i := 0; i < n; i++ {
			missing = append(missing, tok)
		}
	}
	sort.Strings(missing)
	return missing
}

// EvaluateTranslationQuality performs deterministic, zero-cost QA after
// translation. It never calls an LLM, so every chapter can be checked.
func EvaluateTranslationQuality(novelSlug string, chapterNo int, source, translated []string, glossary *model.NovelGlossary) model.TranslationQualityReport {
	report := model.TranslationQualityReport{
		NovelSlug: novelSlug, ChapterNo: chapterNo, Score: 100,
		SourceParagraphs: len(source), TranslatedParagraphs: len(translated),
		Issues: []model.TranslationQualityIssue{}, CheckedAt: time.Now(),
	}
	add := func(code, severity, message string, penalty int) {
		report.Issues = append(report.Issues, model.TranslationQualityIssue{Code: code, Severity: severity, Message: message})
		report.Score -= penalty
	}

	if len(source) > 0 && len(translated) == 0 {
		add("empty_translation", "error", "ไม่มีเนื้อหาคำแปล", 70)
	}
	if len(source) != len(translated) {
		add("paragraph_count", "error",
			fmt.Sprintf("จำนวนย่อหน้าไม่ตรง: ต้นฉบับ %d / แปล %d", len(source), len(translated)), 30)
	}

	for i, p := range translated {
		if HasHanzi(p) {
			add("hanzi_leak", "error", fmt.Sprintf("ยังพบตัวอักษรจีนในย่อหน้า %d", i+1), 40)
			break
		}
	}

	if missing := findMissingNumbers(source, translated); len(missing) > 0 {
		add("number_mismatch", "warning",
			fmt.Sprintf("ตัวเลขจากต้นฉบับหายไปจากคำแปล: %s", strings.Join(missing, ", ")), 10)
	}
	if glossary != nil && len(glossary.Terms) > 0 {
		srcText := strings.Join(source, "\n")
		thText := strings.Join(translated, "\n")
		misses := 0
		for _, term := range glossary.Terms {
			if term.Term == "" || term.Target == "" || !strings.Contains(srcText, term.Term) {
				continue
			}
			if !strings.Contains(thText, term.Target) {
				misses++
				if misses <= 3 {
					add("glossary_mismatch", "warning",
						fmt.Sprintf("พบ %q แต่ไม่พบคำกำหนด %q", term.Term, term.Target), 5)
				}
			}
		}
	}

	if report.Score < 0 {
		report.Score = 0
	}
	return report
}

// ApplySanitizationDiagnostics makes automatic cleanup visible in QA. A model
// that leaked unknown Hanzi should not receive a perfect score just because
// the persistence layer removed those characters afterward.
func ApplySanitizationDiagnostics(report *model.TranslationQualityReport, diag SanitizationDiagnostics) {
	if report == nil || diag.RemovedUnknownHanzi <= 0 {
		return
	}
	severity := "warning"
	penalty := 10 + diag.RemovedUnknownHanzi
	if diag.RemovedUnknownHanzi >= 5 {
		severity = "error"
		penalty += 5
	}
	if penalty > 30 {
		penalty = 30
	}
	message := fmt.Sprintf("คำแปลมีอักษรจีนที่ไม่รู้จักและถูกตัดออก %d ตัว", diag.RemovedUnknownHanzi)
	if len(diag.UnknownSamples) > 0 {
		message += fmt.Sprintf(" (ตัวอย่าง: %s)", strings.Join(diag.UnknownSamples, " "))
	}
	report.Issues = append(report.Issues, model.TranslationQualityIssue{
		Code: "unresolved_hanzi_removed", Severity: severity, Message: message,
	})
	report.Score -= penalty
	if report.Score < 0 {
		report.Score = 0
	}
}
