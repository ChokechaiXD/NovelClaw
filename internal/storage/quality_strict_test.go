package storage

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestListQualityReportsRejectsCorruptReport(t *testing.T) {
	root := t.TempDir()
	qaDir := filepath.Join(root, "bad-qa", "qa")
	if err := os.MkdirAll(qaDir, 0755); err != nil {
		t.Fatal(err)
	}
	payload := append([]byte{0xEF, 0xBB, 0xBF}, []byte(`{"novelSlug":"bad-qa","chapterNo":1,"score":80}`)...)
	if err := os.WriteFile(filepath.Join(qaDir, "0001.json"), payload, 0644); err != nil {
		t.Fatal(err)
	}
	store := NewStore(root)
	if _, err := store.ListQualityReports("bad-qa"); err == nil {
		t.Fatal("expected corrupt QA report to return an error")
	} else if !strings.Contains(err.Error(), "parse quality report 0001.json") {
		t.Fatalf("unexpected error: %v", err)
	}
}
