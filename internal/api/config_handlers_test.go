package api

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"novelclaw/internal/config"
	"novelclaw/internal/storage"
)

func TestUpdateConfigRejectsInvalidTuningBeforeProviderMutation(t *testing.T) {
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = filepath.Join(dir, "novels")
	cfg.ConfigPath = filepath.Join(dir, "config.json")
	router, _ := SetupRouter(cfg, storage.NewStore(cfg.DataDir))

	body := bytes.NewBufferString(`{"provider":"openrouter","routerUrl":"https://openrouter.ai/api/v1","apiKey":"dummy","defaultModel":"vendor/model","parallel":99}`)
	req := httptest.NewRequest(http.MethodPost, "/api/config", body)
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	if active := cfg.ActiveProvider(); active.ID != "9router" {
		t.Fatalf("provider mutated on invalid tuning: %#v", active)
	}
}
