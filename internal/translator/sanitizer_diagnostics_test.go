package translator

import (
	"testing"

	"novelclaw/internal/model"
)

func TestSanitizeTextWithDiagnosticsReportsUnknownHanzi(t *testing.T) {
	cleaned, diag := SanitizeTextWithDiagnostics("ข้อความไทย 測試 จบ", nil)
	if HasHanzi(cleaned) {
		t.Fatalf("cleaned text still has Hanzi: %q", cleaned)
	}
	if diag.RemovedUnknownHanzi != 2 {
		t.Fatalf("RemovedUnknownHanzi=%d, want 2", diag.RemovedUnknownHanzi)
	}
	if len(diag.UnknownSamples) == 0 {
		t.Fatal("expected unknown Hanzi samples")
	}
}

func TestSanitizeKnownHanziDoesNotDamageQA(t *testing.T) {
	_, diag := SanitizeTextWithDiagnostics("ได้รับ 获得 ของ", nil)
	if diag.RemovedUnknownHanzi != 0 {
		t.Fatalf("known glossary term counted as unknown: %#v", diag)
	}

	report := model.TranslationQualityReport{Score: 100}
	ApplySanitizationDiagnostics(&report, diag)
	if report.Score != 100 || len(report.Issues) != 0 {
		t.Fatalf("known repair should not reduce QA: %#v", report)
	}
}
