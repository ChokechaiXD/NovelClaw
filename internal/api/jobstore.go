package api

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"path/filepath"

	"novelclaw/internal/model"
)

// jobsDir returns the directory where pending job specs survive restarts.
func (h *APIHandler) jobsDir() string {
	return filepath.Join(h.cfg.DataDir, ".jobs")
}

// persistJob writes the job spec so an interrupted queue can be resumed
// after a restart. Removed again on completion or cancellation.
func (h *APIHandler) persistJob(jobID string, req model.TranslateRequest) {
	if err := os.MkdirAll(h.jobsDir(), 0755); err != nil {
		return
	}
	data, err := json.Marshal(map[string]interface{}{"jobId": jobID, "request": req})
	if err != nil {
		return
	}
	_ = os.WriteFile(filepath.Join(h.jobsDir(), jobID+".json"), data, 0644)
}

func (h *APIHandler) removeJobFile(jobID string) {
	_ = os.Remove(filepath.Join(h.jobsDir(), jobID+".json"))
}

// ResumeInterruptedJobs restarts translation jobs found on disk at startup.
// Already-translated chapters are skipped by the normal job logic, so a
// resumed batch continues where it died.
func (h *APIHandler) ResumeInterruptedJobs() {
	entries, err := os.ReadDir(h.jobsDir())
	if err != nil {
		return
	}
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".json" {
			continue
		}
		data, err := os.ReadFile(filepath.Join(h.jobsDir(), e.Name()))
		if err != nil {
			continue
		}
		var spec struct {
			JobID   string                `json:"jobId"`
			Request model.TranslateRequest `json:"request"`
		}
		if err := json.Unmarshal(data, &spec); err != nil || spec.JobID == "" {
			_ = os.Remove(filepath.Join(h.jobsDir(), e.Name()))
			continue
		}

		log.Printf("Resuming interrupted job %s (%s ch%d-%d)\n",
			spec.JobID, spec.Request.NovelSlug, spec.Request.StartChapter, spec.Request.EndChapter)

		jobCtx, cancel := context.WithCancel(context.Background())
		h.jobsMu.Lock()
		h.cancels[spec.JobID] = cancel
		h.activeJobs[spec.JobID] = &model.TranslationProgress{
			JobID:          spec.JobID,
			NovelSlug:      spec.Request.NovelSlug,
			TotalChapters:  spec.Request.EndChapter,
			CurrentChapter: spec.Request.StartChapter,
			Status:         "running",
			Percentage:     0,
		}
		h.jobsMu.Unlock()

		go h.runTranslationJob(jobCtx, spec.JobID, spec.Request)
	}
}
