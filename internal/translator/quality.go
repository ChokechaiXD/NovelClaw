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

	srcNumbers := sortedTokens(numberTokenRE.FindAllString(strings.Join(source, " "), -1))
	thNumbers := sortedTokens(numberTokenRE.FindAllString(strings.Join(translated, " "), -1))
	if strings.Join(srcNumbers, "|") != strings.Join(thNumbers, "|") {
		add("number_mismatch", "warning", "ตัวเลขในต้นฉบับและคำแปลไม่ตรงกัน", 10)
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

func sortedTokens(tokens []string) []string {
	out := append([]string(nil), tokens...)
	sort.Strings(out)
	return out
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
