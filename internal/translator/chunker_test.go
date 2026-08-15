package translator

import (
	"strings"
	"testing"
)

func TestSplitParagraphsIntoChunks_Basic(t *testing.T) {
	paras := []string{"Line A", "Line B", "Line C", "Line D", "Line E"}
	chunks := SplitParagraphsIntoChunks(paras, 750)

	if len(chunks) != 1 {
		t.Fatalf("Expected 1 chunk, got %d", len(chunks))
	}
	if len(chunks[0].Paragraphs) != 5 {
		t.Errorf("Expected 5 paragraphs, got %d", len(chunks[0].Paragraphs))
	}
}

func TestSplitParagraphsIntoChunks_MaxParas(t *testing.T) {
	// 30 paragraphs should split at maxParasPerChunk=25
	paras := make([]string, 30)
	for i := range paras {
		paras[i] = "Short paragraph"
	}
	chunks := SplitParagraphsIntoChunks(paras, 750)

	if len(chunks) < 2 {
		t.Fatalf("Expected >= 2 chunks, got %d", len(chunks))
	}
	if len(chunks[0].Paragraphs) > 25 {
		t.Errorf("First chunk has %d paragraphs, max is 25", len(chunks[0].Paragraphs))
	}
}

func TestSplitParagraphsIntoChunks_MaxChars(t *testing.T) {
	// 3 paragraphs of 400 chars each → max 750 chars → should split
	long := strings.Repeat("เ", 400)
	paras := []string{long, long, long}
	chunks := SplitParagraphsIntoChunks(paras, 750)

	if len(chunks) < 2 {
		t.Fatalf("Expected >= 2 chunks due to char limit, got %d", len(chunks))
	}
}

func TestSplitParagraphsIntoChunks_EmptyInput(t *testing.T) {
	chunks := SplitParagraphsIntoChunks(nil, 750)
	if len(chunks) != 0 {
		t.Errorf("Expected 0 chunks for nil input, got %d", len(chunks))
	}

	chunks = SplitParagraphsIntoChunks([]string{}, 750)
	if len(chunks) != 0 {
		t.Errorf("Expected 0 chunks for empty input, got %d", len(chunks))
	}
}

func TestSplitParagraphsIntoChunks_SkipsEmpty(t *testing.T) {
	paras := []string{"A", "", "  ", "B", "\t", "C"}
	chunks := SplitParagraphsIntoChunks(paras, 750)

	total := 0
	for _, c := range chunks {
		total += len(c.Paragraphs)
	}
	if total != 3 {
		t.Errorf("Expected 3 non-empty paragraphs, got %d", total)
	}
}

func TestSplitParagraphsIntoChunks_IndexContinuity(t *testing.T) {
	paras := make([]string, 60)
	for i := range paras {
		paras[i] = "Test paragraph content here"
	}
	chunks := SplitParagraphsIntoChunks(paras, 750)

	for i, c := range chunks {
		if c.Index != i {
			t.Errorf("Chunk[%d].Index = %d, want %d", i, c.Index, i)
		}
	}

	// Verify no paragraph lost
	total := 0
	for _, c := range chunks {
		total += len(c.Paragraphs)
	}
	if total != 60 {
		t.Errorf("Total paragraphs = %d, want 60", total)
	}
}

func TestSplitParagraphsIntoChunks_InvalidMaxChars(t *testing.T) {
	paras := []string{"Hello"}

	// 0 should default to 750
	chunks := SplitParagraphsIntoChunks(paras, 0)
	if len(chunks) != 1 {
		t.Errorf("Expected 1 chunk with default maxChars, got %d", len(chunks))
	}

	// >800 should also default to 750
	chunks = SplitParagraphsIntoChunks(paras, 9999)
	if len(chunks) != 1 {
		t.Errorf("Expected 1 chunk with capped maxChars, got %d", len(chunks))
	}
}
