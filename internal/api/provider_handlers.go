package api

import (
	"context"
	"net/http"
	"strings"
	"time"

	"novelclaw/internal/config"
	"novelclaw/internal/translator"
)

type providerView struct {
	config.ProviderSpec
	Configured bool   `json:"configured"`
	KeyMasked  string `json:"keyMasked,omitempty"`
	Model      string `json:"model,omitempty"`
	Protocol   string `json:"profileProtocol,omitempty"`
	ProfileURL string `json:"profileUrl,omitempty"`
	Active     bool   `json:"active"`
}

func (h *APIHandler) ListProviders(w http.ResponseWriter, r *http.Request) {
	active := h.cfg.GetProvider()
	catalog := config.ProviderCatalog()
	views := make([]providerView, 0, len(catalog))
	for _, spec := range catalog {
		profile := h.cfg.ProviderProfile(spec.ID)
		masked := h.cfg.MaskedKeyForProvider(spec.ID)
		configured := profile.BaseURL != "" && (!spec.KeyRequired || profile.APIKey != "")
		views = append(views, providerView{
			ProviderSpec: spec, Configured: configured,
			KeyMasked: masked, Model: profile.Model, Protocol: profile.Protocol,
			ProfileURL: profile.BaseURL, Active: spec.ID == active,
		})
	}
	WriteJSON(w, http.StatusOK, map[string]interface{}{"active": active, "providers": views})
}

type providerTestRequest struct {
	Provider  string  `json:"provider"`
	BaseURL   string  `json:"baseUrl,omitempty"`
	RouterURL string  `json:"routerUrl,omitempty"`
	APIKey    *string `json:"apiKey,omitempty"`
	Model     string  `json:"model,omitempty"`
	Protocol  string  `json:"protocol,omitempty"`
}

func (h *APIHandler) TestProvider(w http.ResponseWriter, r *http.Request) {
	var payload providerTestRequest
	if err := decodeJSONBody(w, r, &payload, bodyTiny); err != nil {
		WriteError(w, http.StatusBadRequest, "invalid provider settings")
		return
	}
	id := config.NormalizeProviderID(payload.Provider)
	spec, ok := config.ProviderByID(id)
	if !ok {
		id = "custom"
		spec, _ = config.ProviderByID(id)
	}
	profile := h.cfg.ProviderProfile(id)
	candidateURL := payload.BaseURL
	if strings.TrimSpace(candidateURL) == "" {
		candidateURL = payload.RouterURL
	}
	if strings.TrimSpace(candidateURL) != "" {
		profile.BaseURL = strings.TrimRight(strings.TrimSpace(candidateURL), "/")
	}
	if payload.APIKey != nil {
		profile.APIKey = strings.TrimSpace(*payload.APIKey)
	}
	if strings.TrimSpace(payload.Model) != "" {
		profile.Model = strings.TrimSpace(payload.Model)
	}
	if strings.TrimSpace(payload.Protocol) != "" {
		profile.Protocol = strings.TrimSpace(payload.Protocol)
	}
	if strings.TrimSpace(profile.BaseURL) == "" {
		WriteJSON(w, http.StatusBadRequest, map[string]interface{}{
			"ok": false, "provider": id, "error": "provider Base URL is required",
		})
		return
	}
	if spec.KeyRequired && strings.TrimSpace(profile.APIKey) == "" {
		WriteJSON(w, http.StatusBadRequest, map[string]interface{}{
			"ok": false, "provider": id, "error": spec.Name + " requires an API key",
		})
		return
	}

	tmp := config.DefaultConfig()
	tmp.Provider = id
	tmp.RouterURL = profile.BaseURL
	tmp.APIKey = profile.APIKey
	tmp.DefaultModel = profile.Model
	tmp.Providers = map[string]config.ProviderProfile{id: profile}
	client := translator.NewClient(tmp)
	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()
	catalog, err := client.FetchModelCatalogFor(ctx, id)
	if err != nil {
		WriteJSON(w, http.StatusBadGateway, map[string]interface{}{
			"ok": false, "provider": id, "error": err.Error(),
		})
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
		"ok": true, "provider": id, "models": models, "freeModels": freeModels, "modelCount": len(models),
	})
}
