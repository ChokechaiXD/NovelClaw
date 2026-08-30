package api

import (
	"net/http"
	"os"
	"path/filepath"
)

func (h *APIHandler) GetNovelCover(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	candidates := []struct {
		name string
		mime string
	}{
		{"cover.webp", "image/webp"},
		{"cover.jpg", "image/jpeg"},
		{"cover.jpeg", "image/jpeg"},
		{"cover.png", "image/png"},
	}
	for _, candidate := range candidates {
		path := filepath.Join(h.store.DataDir, slug, candidate.name)
		data, err := os.ReadFile(path)
		if err == nil {
			w.Header().Set("Content-Type", candidate.mime)
			w.Header().Set("Cache-Control", "private, max-age=3600")
			w.Header().Set("X-Content-Type-Options", "nosniff")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write(data)
			return
		}
		if !os.IsNotExist(err) {
			WriteError(w, http.StatusInternalServerError, "failed to read novel cover")
			return
		}
	}
	w.WriteHeader(http.StatusNoContent)
}
