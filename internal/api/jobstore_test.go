package api

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"novelclaw/internal/config"
	"novelclaw/internal/storage"
)

func TestResumeInterruptedJobsQuarantinesInvalidFile(t *testing.T) {
	dir := t.TempDir()
	jobsDir := filepath.Join(dir, ".jobs")
	if err := os.MkdirAll(jobsDir, 0755); err != nil {
		t.Fatal(err)
	}
	badPath := filepath.Join(jobsDir, "broken.json")
	if err := os.WriteFile(badPath, []byte("{broken"), 0600); err != nil {
		t.Fatal(err)
	}
	cfg := config.DefaultConfig()
	cfg.DataDir = dir
	h := NewAPIHandler(cfg, storage.NewStore(dir), NewSSEBroker())
	h.ResumeInterruptedJobs()

	if _, err := os.Stat(badPath); !os.IsNotExist(err) {
		t.Fatalf("invalid job was not moved: %v", err)
	}
	entries, err := os.ReadDir(jobsDir)
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, entry := range entries {
		if strings.HasPrefix(entry.Name(), "broken.json.invalid-") {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("quarantined job not found: %v", entries)
	}
}
