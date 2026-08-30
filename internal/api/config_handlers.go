package api

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"novelclaw/internal/config"
)

// ListModels returns models for the requested provider profile. When provider
// is omitted it uses the active profile.
func (h *APIHandler) ListModels(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()
	providerID := r.URL.Query().Get("provider")
	catalog, err := h.translator.FetchModelCatalogFor(ctx, providerID)
	if err != nil {
		WriteError(w, http.StatusBadGateway, fmt.Sprintf("Failed to fetch models: %v", err))
		return
	}
	models := make([]string, 0, len(catalog))
	freeModels := make([]string, 0)
	for _, model := range catalog {
		models = append(models, model.ID)
		if model.Free {
			freeModels = append(freeModels, model.ID)
		}
	}
	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"models": models, "freeModels": freeModels,
	})
}

// GetConfig returns active runtime settings without exposing secrets.
func (h *APIHandler) GetConfig(w http.ResponseWriter, r *http.Request) {
	active := h.cfg.ActiveProvider()
	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"port":         h.cfg.Port,
		"host":         h.cfg.Host,
		"dataDir":      h.cfg.DataDir,
		"provider":     active.ID,
		"routerUrl":    active.BaseURL,
		"apiKey":       h.cfg.MaskedKeyForProvider(active.ID),
		"defaultModel": active.Model,
		"protocol":     active.Protocol,
		"temperature":  h.cfg.GetTemperature(),
		"parallel":     h.cfg.GetParallel(),
		"maxTokens":    h.cfg.GetMaxTokens(),
	})
}

// UpdateConfig saves and activates one provider profile plus global translation
// tuning. A missing apiKey preserves the key already stored for that provider;
// an explicitly empty apiKey clears it.
func (h *APIHandler) UpdateConfig(w http.ResponseWriter, r *http.Request) {
	var payload struct {
		Provider     string   `json:"provider"`
		RouterURL    string   `json:"routerUrl"`
		APIKey       *string  `json:"apiKey,omitempty"`
		DefaultModel string   `json:"defaultModel"`
		Protocol     string   `json:"protocol,omitempty"`
		Temperature  *float64 `json:"temperature,omitempty"`
		Parallel     *int     `json:"parallel,omitempty"`
		MaxTokens    *int     `json:"maxTokens,omitempty"`
	}
	if err := decodeJSONBody(w, r, &payload, bodyTiny); err != nil {
		WriteError(w, http.StatusBadRequest, fmt.Sprintf("Invalid configuration: %v", err))
		return
	}
	providerID := config.NormalizeProviderID(payload.Provider)
	if providerID == "" {
		providerID = h.cfg.GetProvider()
	}
	if payload.Temperature != nil && (*payload.Temperature < 0 || *payload.Temperature > 2) {
		WriteError(w, http.StatusBadRequest, "temperature must be between 0 and 2")
		return
	}
	if payload.Parallel != nil && (*payload.Parallel < 1 || *payload.Parallel > 8) {
		WriteError(w, http.StatusBadRequest, "parallel must be between 1 and 8")
		return
	}
	if payload.MaxTokens != nil && (*payload.MaxTokens < 512 || *payload.MaxTokens > 131072) {
		WriteError(w, http.StatusBadRequest, "maxTokens must be between 512 and 131072")
		return
	}
	if err := h.cfg.ConfigureProviderAndTuning(providerID, payload.RouterURL, payload.APIKey, payload.DefaultModel, payload.Protocol, payload.Temperature, payload.Parallel, payload.MaxTokens); err != nil {
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("Failed to save settings: %v", err))
		return
	}
	h.GetConfig(w, r)
}

// DetectProviders probes well-known local LLM gateways and returns the ones
// that answer on /v1/models, so the settings UI can offer one-click setup
// instead of asking the user to type URLs and keys manually.
func (h *APIHandler) DetectProviders(w http.ResponseWriter, r *http.Request) {
	type probe struct {
		Provider   string `json:"provider"`
		URL        string `json:"url"`
		ModelCount int    `json:"modelCount"`
	}
	candidates := []struct{ name, url string }{
		{"9router", "http://localhost:20128/v1/models"},
		{"ollama", "http://localhost:11434/v1/models"},
		{"lmstudio", "http://localhost:1234/v1/models"},
		{"vllm", "http://localhost:8000/v1/models"},
	}
	client := &http.Client{Timeout: 700 * time.Millisecond}
	results := make([]*probe, len(candidates))
	var wg sync.WaitGroup
	for i, candidate := range candidates {
		i, candidate := i, candidate
		wg.Add(1)
		go func() {
			defer wg.Done()
			req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, candidate.url, nil)
			if err != nil {
				return
			}
			resp, err := client.Do(req) //nolint:gosec // fixed localhost probe only
			if err != nil {
				return
			}
			body, readErr := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
			resp.Body.Close()
			if readErr != nil || resp.StatusCode != http.StatusOK {
				return
			}
			var ml struct {
				Data []json.RawMessage `json:"data"`
			}
			count := 0
			if json.Unmarshal(body, &ml) == nil {
				count = len(ml.Data)
			}
			results[i] = &probe{Provider: candidate.name, URL: candidate.url, ModelCount: count}
		}()
	}
	wg.Wait()
	found := make([]probe, 0, len(candidates))
	for _, result := range results {
		if result != nil {
			found = append(found, *result)
		}
	}
	WriteJSON(w, http.StatusOK, map[string]interface{}{"providers": found})
}
