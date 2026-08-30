package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"novelclaw/internal/config"
	"novelclaw/internal/storage"
)

func TestProviderTestRequiresKeyBeforeNetwork(t *testing.T) {
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = filepath.Join(dir, "novels")
	cfg.ConfigPath = filepath.Join(dir, "config.json")
	router, _ := SetupRouter(cfg, storage.NewStore(cfg.DataDir))
	body := bytes.NewBufferString(`{"provider":"openrouter","routerUrl":"http://127.0.0.1:1","defaultModel":"vendor/model"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/providers/test", body)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	if !strings.Contains(strings.ToLower(w.Body.String()), "api key") {
		t.Fatalf("missing API key error: %s", w.Body.String())
	}
}

func TestModelsEndpointReturnsFreeModels(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"data": []interface{}{
				map[string]interface{}{"id": "vendor/free", "pricing": map[string]string{"prompt": "0", "completion": "0"}},
				map[string]interface{}{"id": "vendor/paid", "pricing": map[string]string{"prompt": "1", "completion": "2"}},
			},
		})
	}))
	defer upstream.Close()
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = filepath.Join(dir, "novels")
	cfg.ConfigPath = filepath.Join(dir, "config.json")
	key := "key"
	if err := cfg.ConfigureProvider("openrouter", upstream.URL, &key, "vendor/paid", "", true); err != nil {
		t.Fatal(err)
	}
	router, _ := SetupRouter(cfg, storage.NewStore(cfg.DataDir))
	req := httptest.NewRequest(http.MethodGet, "/api/models?provider=openrouter", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	var response struct {
		Models     []string `json:"models"`
		FreeModels []string `json:"freeModels"`
	}
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatal(err)
	}
	if len(response.Models) != 2 || len(response.FreeModels) != 1 || response.FreeModels[0] != "vendor/free" {
		t.Fatalf("unexpected model response: %#v", response)
	}
}
