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
	Port         int     `json:"port"`
	Host         string  `json:"host"`
	DataDir      string  `json:"dataDir"`
	RouterURL    string  `json:"routerUrl"`          // e.g. http://localhost:20128/v1
	APIKey       string  `json:"apiKey"`             // 9Router or OpenAI API key
	DefaultModel string  `json:"defaultModel"`       // e.g. google/gemini-2.5-flash or deepseek/deepseek-chat
	Provider     string  `json:"provider,omitempty"` // provider nickname for UI presets (9router, openai, ollama...)
	Temperature  float64 `json:"temperature"`
	Parallel     int     `json:"parallel"`

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
		Port:         4173,
		Host:         "0.0.0.0",
		DataDir:      "./novels",
		RouterURL:    "http://localhost:20128/v1",
		APIKey:       "",
		DefaultModel: "google/gemini-2.5-flash",
		Temperature:  0.3,
		Parallel:     2,
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
		if err := json.Unmarshal(data, cfg); err != nil {
			log.Printf("WARNING: failed to parse %s: %v (using defaults)", configPath, err)
		}
	}

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
	if model := os.Getenv("NOVEL_MODEL"); model != "" {
		cfg.DefaultModel = model
	}

	// Ensure DataDir exists
	_ = os.MkdirAll(cfg.DataDir, 0755)

	return cfg
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
		_ = os.MkdirAll(dir, 0755)
	}
	return os.WriteFile(configPath, data, 0600)
}

// Thread-safe getters for the mutable fields (router URL, key, model, temp).

func (c *AppConfig) GetRouterURL() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.RouterURL
}

func (c *AppConfig) GetAPIKey() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.APIKey
}

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

// MaskedAPIKey returns the API key with only the last 4 characters visible,
// safe for display in API responses and logs.
func (c *AppConfig) MaskedAPIKey() string {
	c.mu.Lock()
	k := c.APIKey
	c.mu.Unlock()
	if k == "" {
		return ""
	}
	if len(k) <= 8 {
		return "****"
	}
	return k[:4] + "…" + k[len(k)-4:]
}
