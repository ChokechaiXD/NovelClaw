package api

import (
	"archive/zip"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"novelclaw/internal/config"
)

func TestCreateBackupAndPrune(t *testing.T) {
	root := t.TempDir()
	cfg := &config.AppConfig{DataDir: filepath.Join(root, "novels")}
	os.MkdirAll(filepath.Join(cfg.DataDir, "global-descent", "chapters"), 0755)
	os.WriteFile(filepath.Join(cfg.DataDir, "global-descent", "chapters", "0001.th.json"), []byte(`{"ok":true}`), 0644)
	os.MkdirAll(filepath.Join(cfg.DataDir, ".cache", "audio"), 0755)
	os.WriteFile(filepath.Join(cfg.DataDir, ".cache", "audio", "cache.mp3"), []byte("regenerable"), 0644)
	os.MkdirAll(filepath.Join(cfg.DataDir, ".jobs"), 0755)
	os.WriteFile(filepath.Join(cfg.DataDir, ".jobs", "pending.json"), []byte(`{"job":true}`), 0644)

	info, err := CreateBackup(cfg)
	if err != nil {
		t.Fatalf("CreateBackup: %v", err)
	}
	if info.SizeMB <= 0 {
		t.Errorf("backup unexpectedly empty: %+v", info)
	}

	// Archive must contain the chapter file.
	zr, err := zip.OpenReader(filepath.Join(backupDir(cfg), info.Name))
	if err != nil {
		t.Fatalf("open archive: %v", err)
	}
	found := false
	foundTransient := false
	for _, f := range zr.File {
		if f.Name == "novels/global-descent/chapters/0001.th.json" {
			found = true
		}
		if strings.Contains(f.Name, "/.cache/") || strings.Contains(f.Name, "/.jobs/") {
			foundTransient = true
		}
	}
	zr.Close() // release the handle BEFORE rotating: Windows can't delete open files
	if !found {
		t.Error("chapter file missing from archive")
	}
	if foundTransient {
		t.Error("backup must exclude regenerable cache and transient job files")
	}

	// Rotation: create backupKeep+2 archives, oldest must be pruned.
	for i := 0; i < backupKeep+2; i++ {
		if _, err := CreateBackup(cfg); err != nil {
			t.Fatalf("CreateBackup %d: %v", i, err)
		}
	}
	list := ListBackups(cfg)
	if len(list) != backupKeep {
		t.Errorf("retention broken: got %d backups, want %d", len(list), backupKeep)
	}
}

func TestConcurrentBackupsAreCompleteAndLeaveNoTempArchives(t *testing.T) {
	root := t.TempDir()
	cfg := &config.AppConfig{DataDir: filepath.Join(root, "novels")}
	if err := os.MkdirAll(filepath.Join(cfg.DataDir, "book"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(cfg.DataDir, "book", "novel.json"), []byte(`{"title":"book"}`), 0644); err != nil {
		t.Fatal(err)
	}

	const workers = 4
	var wg sync.WaitGroup
	errs := make(chan error, workers)
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := CreateBackup(cfg)
			errs <- err
		}()
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatal(err)
		}
	}
	entries, err := os.ReadDir(backupDir(cfg))
	if err != nil {
		t.Fatal(err)
	}
	zipCount := 0
	for _, entry := range entries {
		if strings.HasSuffix(entry.Name(), ".tmp") {
			t.Fatalf("partial backup leaked into directory: %s", entry.Name())
		}
		if strings.HasSuffix(entry.Name(), ".zip") {
			zipCount++
			zr, err := zip.OpenReader(filepath.Join(backupDir(cfg), entry.Name()))
			if err != nil {
				t.Fatalf("unreadable backup %s: %v", entry.Name(), err)
			}
			_ = zr.Close()
		}
	}
	if zipCount != workers {
		t.Fatalf("zip count=%d want=%d", zipCount, workers)
	}
}
