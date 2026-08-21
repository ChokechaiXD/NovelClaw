package api

import (
	"archive/zip"
	"os"
	"path/filepath"
	"testing"

	"novelclaw/internal/config"
)

func TestCreateBackupAndPrune(t *testing.T) {
	root := t.TempDir()
	cfg := &config.AppConfig{DataDir: filepath.Join(root, "novels")}
	os.MkdirAll(filepath.Join(cfg.DataDir, "global-descent", "chapters"), 0755)
	os.WriteFile(filepath.Join(cfg.DataDir, "global-descent", "chapters", "0001.th.json"), []byte(`{"ok":true}`), 0644)

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
	for _, f := range zr.File {
		if f.Name == "novels/global-descent/chapters/0001.th.json" {
			found = true
		}
	}
	zr.Close() // release the handle BEFORE rotating: Windows can't delete open files
	if !found {
		t.Error("chapter file missing from archive")
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
