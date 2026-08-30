package config

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"sync"
)

// AppConfig contains runtime settings for NovelClaw
type AppConfig struct {
	Port         int                        `json:"port"`
	Host         string                     `json:"host"`
	DataDir      string                     `json:"dataDir"`
	RouterURL    string                     `json:"routerUrl"`          // e.g. http://localhost:20128/v1
	APIKey       string                     `json:"apiKey"`             // 9Router or OpenAI API key
	DefaultModel string                     `json:"defaultModel"`       // e.g. google/gemini-2.5-flash or deepseek/deepseek-chat
	Provider     string                     `json:"provider,omitempty"` // active provider profile ID
	Providers    map[string]ProviderProfile `json:"providers,omitempty"`
	Temperature  float64                    `json:"temperature"`
	Parallel     int                        `json:"parallel"`
	MaxTokens    int                        `json:"maxTokens,omitempty"` // LLM completion cap (default 8192)

	// ConfigPath remembers the file this config was loaded from / should be
	// saved back to. Not serialized.
	ConfigPath string `json:"-"`

	// mu guards concurrent reads/writes of the mutable fields above
	// (HTTP handlers mutate config while the translator client reads it).
	mu sync.Mutex `json:"-"`
}

// DefaultConfig returns safe out-of-the-box defaults
func DefaultConfig() *AppConfig {
	return &AppConfig{
		Port:         4890,
		Host:         "0.0.0.0",
		DataDir:      "./novels",
		RouterURL:    "http://localhost:20128/v1",
		APIKey:       "",
		DefaultModel: "google/gemini-2.5-flash",
		Provider:     "9router",
		Providers: map[string]ProviderProfile{
			"9router": {BaseURL: "http://localhost:20128/v1", Model: "google/gemini-2.5-flash", Protocol: ProtocolOpenAIChat},
		},
		Temperature: 0.3,
		Parallel:    2,
	}
}

// LoadConfig loads configuration from config.json, environment variables, or defaults
func LoadConfig(configPath string) *AppConfig {
	cfg := DefaultConfig()

	// Load from JSON file if exists
	if configPath == "" {
		configPath = "config.json"
	}
	cfg.ConfigPath = configPath

	if data, err := os.ReadFile(configPath); err == nil {
		// Do not merge persisted data into the default provider-profile map.
		// Legacy configs have only routerUrl/apiKey/defaultModel; leaving the
		// default map populated would make those user values lose to presets.
		cfg.Providers = nil
		if err := json.Unmarshal(data, cfg); err != nil {
			log.Printf("WARNING: failed to parse %s: %v", configPath, err)
			if recovered, recoverErr := loadConfigBackup(configPath); recoverErr == nil {
				cfg = recovered
				cfg.ConfigPath = configPath
				log.Printf("Recovered configuration from %s.bak", configPath)
			} else {
				cfg = DefaultConfig()
				cfg.ConfigPath = configPath
				log.Printf("WARNING: no valid config backup available: %v (using defaults)", recoverErr)
			}
		}
	} else if !os.IsNotExist(err) {
		log.Printf("WARNING: failed to read %s: %v (using defaults)", configPath, err)
	}

	// Modern provider profiles are the source of truth. The config object was
	// initialized with legacy defaults before JSON unmarshal, so without this
	// step an omitted routerUrl/defaultModel could overwrite a persisted profile.
	cfg.preferActiveProviderProfile()

	// Override with environment variables
	if portStr := os.Getenv("PORT"); portStr != "" {
		if p, err := strconv.Atoi(portStr); err == nil {
			cfg.Port = p
		}
	}
	if host := os.Getenv("HOST"); host != "" {
		cfg.Host = host
	}
	if dataDir := os.Getenv("DATA_DIR"); dataDir != "" {
		cfg.DataDir = dataDir
	}
	if routerURL := os.Getenv("NINEROUTER_URL"); routerURL != "" {
		cfg.RouterURL = routerURL
	} else if openAIURL := os.Getenv("OPENAI_BASE_URL"); openAIURL != "" {
		cfg.RouterURL = openAIURL
	}
	if apiKey := os.Getenv("NINEROUTER_KEY"); apiKey != "" {
		cfg.APIKey = apiKey
	} else if cfg.APIKey == "" {
		if apiKey := os.Getenv("OPENROUTER_API_KEY"); apiKey != "" {
			cfg.APIKey = apiKey
		} else if apiKey := os.Getenv("OPENAI_API_KEY"); apiKey != "" {
			cfg.APIKey = apiKey
		}
	}
	if provider := os.Getenv("NOVEL_PROVIDER"); provider != "" {
		cfg.Provider = NormalizeProviderID(provider)
	}
	if model := os.Getenv("NOVEL_MODEL"); model != "" {
		cfg.DefaultModel = model
	}

	// Migrate legacy single-provider settings and keep the active profile in
	// sync. Existing config.json files continue to work without manual edits.
	cfg.normalizeProviders()

	// Ensure DataDir exists. Loading still returns a config for compatibility,
	// but surface startup filesystem problems immediately in the log.
	if err := os.MkdirAll(cfg.DataDir, 0755); err != nil {
		log.Printf("ERROR: cannot create data directory %s: %v", cfg.DataDir, err)
	}

	return cfg
}

func (c *AppConfig) preferActiveProviderProfile() {
	if len(c.Providers) == 0 {
		return
	}
	id := NormalizeProviderID(c.Provider)
	profile, ok := c.Providers[id]
	if !ok {
		return
	}
	c.RouterURL = profile.BaseURL
	c.APIKey = profile.APIKey
	c.DefaultModel = profile.Model
}

// Save writes current configuration back to disk. If configPath is empty,
// the path the config was loaded from is used. Safe for concurrent use.
func (c *AppConfig) Save(configPath string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.saveLocked(configPath)
}

// Update atomically mutates the config under its lock and persists the
// result to the loaded config file.
func (c *AppConfig) Update(mutate func(*AppConfig)) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	mutate(c)
	return c.saveLocked("")
}

func loadConfigBackup(configPath string) (*AppConfig, error) {
	data, err := os.ReadFile(configPath + ".bak")
	if err != nil {
		return nil, err
	}
	cfg := DefaultConfig()
	cfg.Providers = nil
	if err := json.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("parse backup: %w", err)
	}
	return cfg, nil
}

func (c *AppConfig) saveLocked(configPath string) error {
	if configPath == "" {
		configPath = c.ConfigPath
	}
	if configPath == "" {
		return fmt.Errorf("no config file path set; refusing to write")
	}
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	dir := filepath.Dir(configPath)
	if dir != "." && dir != "" {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return fmt.Errorf("create config directory: %w", err)
		}
	}
	// Atomic write: a crash mid-save must not leave a truncated config.json
	// behind (the app would then boot with defaults and lose the API key).
	tmp := configPath + ".tmp"
	if err := os.WriteFile(tmp, data, 0600); err != nil {
		return err
	}
	if err := os.Rename(tmp, configPath); err != nil {
		_ = os.Remove(tmp)
		return err
	}

	// Keep a last-known-good recovery copy. Failure to refresh the backup does
	// not roll back a successful settings save, but it is surfaced in logs.
	backupTmp := configPath + ".bak.tmp"
	if err := os.WriteFile(backupTmp, data, 0600); err != nil {
		log.Printf("WARNING: failed to refresh config backup: %v", err)
		return nil
	}
	if err := os.Rename(backupTmp, configPath+".bak"); err != nil {
		_ = os.Remove(backupTmp)
		log.Printf("WARNING: failed to activate config backup: %v", err)
	}
	return nil
}

// Thread-safe getters for mutable runtime settings. Provider URL/key access
// goes through ActiveProvider/ProviderRuntime in providers.go.
func (c *AppConfig) GetDefaultModel() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.DefaultModel
}

func (c *AppConfig) GetTemperature() float64 {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.Temperature
}

func (c *AppConfig) GetProvider() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.Provider
}

func (c *AppConfig) GetParallel() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.Parallel <= 0 {
		return 1
	}
	return c.Parallel
}

// GetMaxTokens returns the LLM completion token cap (default 8192 when unset).
func (c *AppConfig) GetMaxTokens() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.MaxTokens <= 0 {
		return 8192
	}
	return c.MaxTokens
}
