package config

import (
	"net/url"
	"strings"
)

const (
	ProtocolOpenAIChat      = "openai-chat"
	ProtocolOpenAIResponses = "openai-responses"
	ProtocolAnthropic       = "anthropic-messages"
	ProtocolOpenCodeZen     = "opencode-zen"
)

type ProviderProfile struct {
	BaseURL  string `json:"baseUrl"`
	APIKey   string `json:"apiKey,omitempty"`
	Model    string `json:"model,omitempty"`
	Protocol string `json:"protocol,omitempty"`
}

type ProviderSpec struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	BaseURL     string   `json:"baseUrl"`
	Protocol    string   `json:"protocol"`
	Local       bool     `json:"local"`
	KeyRequired bool     `json:"keyRequired"`
	ModelHints  []string `json:"modelHints,omitempty"`
	FreeModels  []string `json:"freeModels,omitempty"`
}

var providerCatalog = []ProviderSpec{
	{ID: "9router", Name: "9Router", Description: "Local AI gateway (9Router / Node Router compatible)", BaseURL: "http://localhost:20128/v1", Protocol: ProtocolOpenAIChat, Local: true},
	{ID: "openrouter", Name: "OpenRouter", Description: "Multi-provider model gateway with free-model routing", BaseURL: "https://openrouter.ai/api/v1", Protocol: ProtocolOpenAIChat, KeyRequired: true, FreeModels: []string{"openrouter/free"}},
	{ID: "opencode-zen", Name: "OpenCode Zen", Description: "Curated OpenCode gateway; free models are detected live (Zen API key still required)", BaseURL: "https://opencode.ai/zen/v1", Protocol: ProtocolOpenCodeZen, KeyRequired: true},
	{ID: "gemini", Name: "Google Gemini", Description: "Gemini API via OpenAI compatibility", BaseURL: "https://generativelanguage.googleapis.com/v1beta/openai", Protocol: ProtocolOpenAIChat, KeyRequired: true, ModelHints: []string{"gemini-3.7-flash", "gemini-3.1-pro"}},
	{ID: "anthropic", Name: "Anthropic Claude", Description: "Native Claude Messages API", BaseURL: "https://api.anthropic.com/v1", Protocol: ProtocolAnthropic, KeyRequired: true, ModelHints: []string{"claude-sonnet-5", "claude-opus-5"}},
	{ID: "deepseek", Name: "DeepSeek", Description: "DeepSeek official API", BaseURL: "https://api.deepseek.com", Protocol: ProtocolOpenAIChat, KeyRequired: true, ModelHints: []string{"deepseek-v4-flash", "deepseek-v4-pro"}},
	{ID: "openai", Name: "OpenAI", Description: "OpenAI API", BaseURL: "https://api.openai.com/v1", Protocol: ProtocolOpenAIChat, KeyRequired: true},
	{ID: "groq", Name: "Groq", Description: "Low-latency OpenAI-compatible inference", BaseURL: "https://api.groq.com/openai/v1", Protocol: ProtocolOpenAIChat, KeyRequired: true, ModelHints: []string{"openai/gpt-oss-20b", "openai/gpt-oss-120b"}},
	{ID: "mistral", Name: "Mistral AI", Description: "Mistral OpenAI-compatible API", BaseURL: "https://api.mistral.ai/v1", Protocol: ProtocolOpenAIChat, KeyRequired: true, ModelHints: []string{"mistral-small-latest", "mistral-large-latest"}},
	{ID: "xai", Name: "xAI Grok", Description: "xAI OpenAI-compatible API", BaseURL: "https://api.x.ai/v1", Protocol: ProtocolOpenAIChat, KeyRequired: true, ModelHints: []string{"grok-4.6"}},
	{ID: "ollama", Name: "Ollama", Description: "Local Ollama OpenAI compatibility", BaseURL: "http://localhost:11434/v1", Protocol: ProtocolOpenAIChat, Local: true},
	{ID: "lmstudio", Name: "LM Studio", Description: "Local LM Studio server", BaseURL: "http://localhost:1234/v1", Protocol: ProtocolOpenAIChat, Local: true},
	{ID: "vllm", Name: "vLLM", Description: "Local/self-hosted vLLM server", BaseURL: "http://localhost:8000/v1", Protocol: ProtocolOpenAIChat, Local: true},
	{ID: "custom", Name: "Custom", Description: "Any compatible endpoint", BaseURL: "", Protocol: ProtocolOpenAIChat},
}

func ProviderCatalog() []ProviderSpec {
	out := make([]ProviderSpec, len(providerCatalog))
	copy(out, providerCatalog)
	return out
}

func ProviderByID(id string) (ProviderSpec, bool) {
	id = NormalizeProviderID(id)
	for _, p := range providerCatalog {
		if p.ID == id {
			return p, true
		}
	}
	return ProviderSpec{}, false
}
func NormalizeProviderID(id string) string {
	id = strings.ToLower(strings.TrimSpace(id))
	switch id {
	case "ninerouter", "node-router", "node_router", "9-router":
		return "9router"
	case "google", "google-gemini":
		return "gemini"
	case "claude":
		return "anthropic"
	case "opencode", "zen", "opencodezen":
		return "opencode-zen"
	case "lm-studio":
		return "lmstudio"
	default:
		return id
	}
}

func InferProviderID(baseURL string) string {
	u := strings.ToLower(baseURL)
	checks := []struct{ needle, id string }{
		{"opencode.ai/zen", "opencode-zen"}, {"openrouter.ai", "openrouter"},
		{"generativelanguage.googleapis.com", "gemini"}, {"api.anthropic.com", "anthropic"},
		{"api.deepseek.com", "deepseek"}, {"api.openai.com", "openai"},
		{"api.groq.com", "groq"}, {"api.mistral.ai", "mistral"}, {"api.x.ai", "xai"},
		{"localhost:20128", "9router"}, {"localhost:11434", "ollama"},
		{"localhost:1234", "lmstudio"}, {"localhost:8000", "vllm"},
	}
	for _, c := range checks {
		if strings.Contains(u, c.needle) {
			return c.id
		}
	}
	return "custom"
}

type ActiveProvider struct {
	ID          string
	Name        string
	BaseURL     string
	APIKey      string
	Model       string
	Protocol    string
	Local       bool
	KeyRequired bool
}

func (c *AppConfig) normalizeProviders() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.normalizeProvidersLocked()
}

func (c *AppConfig) normalizeProvidersLocked() {
	if c.Providers == nil {
		c.Providers = make(map[string]ProviderProfile)
	}
	id := NormalizeProviderID(c.Provider)
	inferred := InferProviderID(c.RouterURL)
	if id == "" || (id == "9router" && inferred != "9router" && inferred != "custom") {
		id = inferred
	}
	if _, ok := ProviderByID(id); !ok {
		id = "custom"
	}
	spec, _ := ProviderByID(id)
	profile, exists := c.Providers[id]
	if !exists {
		profile = ProviderProfile{
			BaseURL:  strings.TrimRight(strings.TrimSpace(c.RouterURL), "/"),
			APIKey:   c.APIKey,
			Model:    c.DefaultModel,
			Protocol: spec.Protocol,
		}
	} else {
		legacyMatchesProvider := c.RouterURL != "" && (InferProviderID(c.RouterURL) == id || id == "custom")
		if legacyMatchesProvider {
			profile.BaseURL = strings.TrimRight(strings.TrimSpace(c.RouterURL), "/")
			if c.APIKey != "" {
				profile.APIKey = c.APIKey
			}
			if c.DefaultModel != "" {
				profile.Model = c.DefaultModel
			}
		} else {
			if profile.BaseURL == "" {
				profile.BaseURL = spec.BaseURL
			}
			if profile.Model == "" && c.DefaultModel != "" {
				profile.Model = c.DefaultModel
			}
		}
	}
	if profile.BaseURL == "" {
		profile.BaseURL = spec.BaseURL
	}
	if profile.Protocol == "" {
		profile.Protocol = spec.Protocol
	}
	c.Providers[id] = profile
	c.Provider = id
	c.syncLegacyLocked(profile)
}
func (c *AppConfig) syncLegacyLocked(profile ProviderProfile) {
	c.RouterURL = profile.BaseURL
	c.APIKey = profile.APIKey
	c.DefaultModel = profile.Model
}

func (c *AppConfig) ActiveProvider() ActiveProvider {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.normalizeProvidersLocked()
	profile := c.Providers[c.Provider]
	spec, _ := ProviderByID(c.Provider)
	return ActiveProvider{
		ID: c.Provider, Name: spec.Name, BaseURL: profile.BaseURL,
		APIKey: profile.APIKey, Model: profile.Model, Protocol: profile.Protocol,
		Local: spec.Local, KeyRequired: spec.KeyRequired,
	}
}

func (c *AppConfig) ProviderProfile(id string) ProviderProfile {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.normalizeProvidersLocked()
	id = NormalizeProviderID(id)
	profile := c.Providers[id]
	if spec, ok := ProviderByID(id); ok {
		if profile.BaseURL == "" {
			profile.BaseURL = spec.BaseURL
		}
		if profile.Protocol == "" {
			profile.Protocol = spec.Protocol
		}
	}
	return profile
}
func (c *AppConfig) configureProviderLocked(id, baseURL string, apiKey *string, model, protocol string, activate bool) {
	id = NormalizeProviderID(id)
	spec, known := ProviderByID(id)
	if !known {
		id = "custom"
		spec, _ = ProviderByID(id)
	}
	profile := c.Providers[id]
	oldBaseURL := profile.BaseURL
	baseURL = strings.TrimRight(strings.TrimSpace(baseURL), "/")
	if baseURL != "" {
		profile.BaseURL = baseURL
	}
	if profile.BaseURL == "" {
		profile.BaseURL = spec.BaseURL
	}
	// Never forward a saved secret to a different network origin implicitly.
	if apiKey == nil && oldBaseURL != "" && !sameProviderOrigin(oldBaseURL, profile.BaseURL) {
		profile.APIKey = ""
	}
	if apiKey != nil {
		profile.APIKey = strings.TrimSpace(*apiKey)
	}
	if strings.TrimSpace(model) != "" {
		profile.Model = strings.TrimSpace(model)
	}
	if strings.TrimSpace(protocol) != "" {
		profile.Protocol = strings.TrimSpace(protocol)
	}
	if profile.Protocol == "" {
		profile.Protocol = spec.Protocol
	}
	c.Providers[id] = profile
	if activate {
		c.Provider = id
		c.syncLegacyLocked(profile)
	}
}

func (c *AppConfig) ConfigureProvider(id, baseURL string, apiKey *string, model, protocol string, activate bool) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.normalizeProvidersLocked()
	c.configureProviderLocked(id, baseURL, apiKey, model, protocol, activate)
	return c.saveLocked("")
}

// ConfigureProviderAndTuning commits the provider profile and global runtime
// tuning in one atomic config write, avoiding partially-applied settings.
func (c *AppConfig) ConfigureProviderAndTuning(id, baseURL string, apiKey *string, model, protocol string, temperature *float64, parallel, maxTokens *int) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.normalizeProvidersLocked()
	c.configureProviderLocked(id, baseURL, apiKey, model, protocol, true)
	if temperature != nil {
		c.Temperature = *temperature
	}
	if parallel != nil {
		c.Parallel = *parallel
	}
	if maxTokens != nil {
		c.MaxTokens = *maxTokens
	}
	return c.saveLocked("")
}
func (c *AppConfig) SetActiveModel(model string) error {
	model = strings.TrimSpace(model)
	if model == "" {
		return nil
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	c.normalizeProvidersLocked()
	profile := c.Providers[c.Provider]
	profile.Model = model
	c.Providers[c.Provider] = profile
	c.syncLegacyLocked(profile)
	return c.saveLocked("")
}

func (c *AppConfig) MaskedKeyForProvider(id string) string {
	profile := c.ProviderProfile(id)
	k := profile.APIKey
	if k == "" {
		return ""
	}
	if len(k) <= 8 {
		return "****"
	}
	return k[:4] + "…" + k[len(k)-4:]
}
func (c *AppConfig) ProviderRuntime(id string) ActiveProvider {
	if strings.TrimSpace(id) == "" {
		return c.ActiveProvider()
	}
	id = NormalizeProviderID(id)
	profile := c.ProviderProfile(id)
	spec, _ := ProviderByID(id)
	return ActiveProvider{
		ID: id, Name: spec.Name, BaseURL: profile.BaseURL,
		APIKey: profile.APIKey, Model: profile.Model, Protocol: profile.Protocol,
		Local: spec.Local, KeyRequired: spec.KeyRequired,
	}
}

func sameProviderOrigin(a, b string) bool {
	ua, errA := url.Parse(strings.TrimSpace(a))
	ub, errB := url.Parse(strings.TrimSpace(b))
	if errA != nil || errB != nil || ua.Host == "" || ub.Host == "" {
		return strings.EqualFold(strings.TrimRight(a, "/"), strings.TrimRight(b, "/"))
	}
	return strings.EqualFold(ua.Scheme, ub.Scheme) && strings.EqualFold(ua.Host, ub.Host)
}

// ApplyRuntimeProviderOverride applies CLI-only provider overrides without
// persisting them. All runtime paths still go through the same provider
// registry, so --router/--key/--model cannot drift from ActiveProvider().
func (c *AppConfig) ApplyRuntimeProviderOverride(baseURL, apiKey, model string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.normalizeProvidersLocked()

	id := c.Provider
	if strings.TrimSpace(baseURL) != "" {
		id = InferProviderID(baseURL)
		if _, ok := ProviderByID(id); !ok {
			id = "custom"
		}
	}
	spec, _ := ProviderByID(id)
	profile := c.Providers[id]
	if strings.TrimSpace(baseURL) != "" {
		profile.BaseURL = strings.TrimRight(strings.TrimSpace(baseURL), "/")
	}
	if profile.BaseURL == "" {
		profile.BaseURL = spec.BaseURL
	}
	if strings.TrimSpace(apiKey) != "" {
		profile.APIKey = strings.TrimSpace(apiKey)
	}
	if strings.TrimSpace(model) != "" {
		profile.Model = strings.TrimSpace(model)
	}
	if profile.Protocol == "" {
		profile.Protocol = spec.Protocol
	}
	c.Providers[id] = profile
	c.Provider = id
	c.syncLegacyLocked(profile)
}
