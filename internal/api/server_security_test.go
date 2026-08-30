package api

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"novelclaw/internal/config"
	"novelclaw/internal/storage"
)

func securityTestRouter(t *testing.T) http.Handler {
	t.Helper()
	dir := t.TempDir()
	cfg := config.DefaultConfig()
	cfg.DataDir = filepath.Join(dir, "novels")
	cfg.ConfigPath = filepath.Join(dir, "config.json")
	router, _ := SetupRouter(cfg, storage.NewStore(cfg.DataDir))
	return router
}

func TestServerRejectsCrossOriginAPIRequests(t *testing.T) {
	router := securityTestRouter(t)
	req := httptest.NewRequest(http.MethodGet, "http://novelclaw.local/api/providers", nil)
	req.Host = "novelclaw.local"
	req.Header.Set("Origin", "https://evil.example")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusForbidden {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
}
func TestServerAllowsSameOriginAndSetsSecurityHeaders(t *testing.T) {
	router := securityTestRouter(t)
	req := httptest.NewRequest(http.MethodGet, "http://novelclaw.local/api/providers", nil)
	req.Host = "novelclaw.local"
	req.Header.Set("Origin", "http://novelclaw.local")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	if got := w.Header().Get("Access-Control-Allow-Origin"); got != "http://novelclaw.local" {
		t.Fatalf("allow-origin=%q", got)
	}
	if got := w.Header().Get("X-Content-Type-Options"); got != "nosniff" {
		t.Fatalf("nosniff header=%q", got)
	}
	if got := w.Header().Get("Content-Security-Policy"); got == "" {
		t.Fatal("missing Content-Security-Policy")
	}
}

func TestEmbeddedFrontendModulesAreServed(t *testing.T) {
	router := securityTestRouter(t)
	for path, needle := range map[string]string{
		"/":                      `type="module" src="/app.js"`,
		"/js/providers.js":       "createProviderController",
		"/js/tts.js":             "createTTSController",
		"/js/jobs.js":            "createJobController",
		"/js/library.js":         "createLibraryController",
		"/js/intelligence.js":    "createIntelligenceController",
		"/js/glossary.js":        "createGlossaryController",
		"/js/export.js":          "createExportController",
		"/js/reader.js":          "createReaderController",
		"/js/workflow.js":        "createWorkflowController",
		"/js/provider_events.js": "createProviderEvents",
		"/js/state.js":           "createInitialState",
		"/js/dom.js":             "bindDOM",
		"/js/api.js":             "createAPIClient",
		"/js/utils.js":           "escapeHTML",
	} {
		req := httptest.NewRequest(http.MethodGet, "http://novelclaw.local"+path, nil)
		req.Host = "novelclaw.local"
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("GET %s status=%d body=%s", path, w.Code, w.Body.String())
		}
		if !strings.Contains(w.Body.String(), needle) {
			t.Fatalf("GET %s missing %q", path, needle)
		}
	}
}

func TestServerRejectsCrossOriginSSE(t *testing.T) {
	router := securityTestRouter(t)
	req := httptest.NewRequest(http.MethodGet, "http://novelclaw.local/events", nil)
	req.Host = "novelclaw.local"
	req.Header.Set("Origin", "https://evil.example")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusForbidden {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
}
