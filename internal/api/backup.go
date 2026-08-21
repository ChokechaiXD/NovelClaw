package api

import (
	"archive/zip"
	"fmt"
	"io"
	"io/fs"
	"log"
	"math/rand/v2"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"novelclaw/internal/config"
)

// backupKeep is how many recent archives to retain (older ones are deleted).
// ponytail: fixed retention; make it configurable when the first user hits it.
const backupKeep = 7

// backupStaleAfter is how long an auto backup may lag behind startup.
const backupStaleAfter = 24 * time.Hour

type backupInfo struct {
	Name    string    `json:"name"`
	SizeMB  float64   `json:"sizeMB"`
	ModTime time.Time `json:"modTime"`
}

func backupDir(cfg *config.AppConfig) string {
	return filepath.Join(filepath.Dir(cfg.DataDir), "backups")
}

// CreateBackup zips the whole data directory into backups/<timestamp>.zip
// and prunes old archives beyond backupKeep.
func CreateBackup(cfg *config.AppConfig) (backupInfo, error) {
	dir := backupDir(cfg)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return backupInfo{}, err
	}

	// ponytail: random suffix defeats Windows clock granularity (~2ms) which
	// can hand out identical timestamps to back-to-back backups.
	name := fmt.Sprintf("novelclaw-backup-%s-%04x.zip", time.Now().Format("20060102-150405"), rand.IntN(0xffff))
	dest := filepath.Join(dir, name)

	out, err := os.Create(dest)
	if err != nil {
		return backupInfo{}, err
	}

	zw := zip.NewWriter(out)
	err = filepath.WalkDir(cfg.DataDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		rel, err := filepath.Rel(filepath.Dir(cfg.DataDir), path)
		if err != nil {
			return nil // skip entries outside the root
		}
		w, err := zw.Create(filepath.ToSlash(rel))
		if err != nil {
			return err
		}
		src, err := os.Open(path)
		if err != nil {
			return err
		}
		defer src.Close()
		_, err = io.Copy(w, src)
		return err
	})
	if err != nil {
		out.Close()
		os.Remove(dest)
		return backupInfo{}, err
	}
	if err := zw.Close(); err != nil {
		out.Close()
		os.Remove(dest)
		return backupInfo{}, err
	}
	// Close before pruning: an open handle blocks deletion on Windows.
	if err := out.Close(); err != nil {
		os.Remove(dest)
		return backupInfo{}, err
	}

	pruneBackups(dir)

	info, err := os.Stat(dest)
	if err != nil {
		return backupInfo{}, err
	}
	return backupInfo{Name: name, SizeMB: float64(info.Size()) / (1 << 20), ModTime: info.ModTime()}, nil
}

// ListBackups returns retained archives, newest first.
func ListBackups(cfg *config.AppConfig) []backupInfo {
	dir := backupDir(cfg)
	entries, err := os.ReadDir(dir)
	if err != nil {
		return []backupInfo{}
	}
	var list []backupInfo
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".zip") {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		list = append(list, backupInfo{
			Name:    e.Name(),
			SizeMB:  float64(info.Size()) / (1 << 20),
			ModTime: info.ModTime(),
		})
	}
	sort.Slice(list, func(i, j int) bool { return list[i].ModTime.After(list[j].ModTime) })
	return list
}

func pruneBackups(dir string) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	type archive struct {
		path string
		mod  time.Time
	}
	var list []archive
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".zip") {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		list = append(list, archive{filepath.Join(dir, e.Name()), info.ModTime()})
	}
	sort.Slice(list, func(i, j int) bool { return list[i].mod.Before(list[j].mod) })
	for len(list) > backupKeep {
		_ = os.Remove(list[0].path)
		list = list[1:]
	}
}

// MaybeAutoBackup creates a fresh backup at startup when the newest one is
// older than backupStaleAfter (or none exists).
func MaybeAutoBackup(cfg *config.AppConfig) {
	list := ListBackups(cfg)
	if len(list) > 0 && time.Since(list[0].ModTime) < backupStaleAfter {
		return
	}
	info, err := CreateBackup(cfg)
	if err != nil {
		log.Printf("Auto backup failed: %v", err)
		return
	}
	log.Printf("Auto backup created: %s (%.1f MB)", info.Name, info.SizeMB)
}

// BackupNow handles POST /api/backup.
func (h *APIHandler) BackupNow(w http.ResponseWriter, r *http.Request) {
	info, err := CreateBackup(h.cfg)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("Backup failed: %v", err))
		return
	}
	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"status":   "created",
		"backup":   info,
		"archives": ListBackups(h.cfg),
	})
}

// ListBackupsHandler handles GET /api/backup.
func (h *APIHandler) ListBackupsHandler(w http.ResponseWriter, r *http.Request) {
	WriteJSON(w, http.StatusOK, map[string]interface{}{"archives": ListBackups(h.cfg)})
}
