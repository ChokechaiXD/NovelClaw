package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	if cfg.Port != 4173 {
		t.Errorf("Default Port = %d, want 4173", cfg.Port)
	}
	if cfg.Host != "0.0.0.0" {
		t.Errorf("Default Host = %q, want 0.0.0.0", cfg.Host)
	}
	if cfg.DataDir != "./novels" {
		t.Errorf("Default DataDir = %q, want ./novels", cfg.DataDir)
	}
	if cfg.Temperature != 0.3 {
		t.Errorf("Default Temperature = %f, want 0.3", cfg.Temperature)
	}
	if cfg.Parallel != 2 {
		t.Errorf("Default Parallel = %d, want 2", cfg.Parallel)
	}
	if cfg.DefaultModel != "google/gemini-2.5-flash" {
		t.Errorf("Default Model = %q, want google/gemini-2.5-flash", cfg.DefaultModel)
	}
}

func TestLoadConfigFromFile(t *testing.T) {
	dir := t.TempDir()
	cfgPath := filepath.Join(dir, "config.json")

	// Write a test config file
	data, _ := json.MarshalIndent(AppConfig{
		Port:         9999,
		Host:         "127.0.0.1",
		DataDir:      "/tmp/novels",
		DefaultModel: "deepseek/deepseek-chat",
		Temperature:  0.7,
	}, "", "  ")
	os.WriteFile(cfgPath, data, 0644)

	cfg := LoadConfig(cfgPath)

	if cfg.Port != 9999 {
		t.Errorf("Port = %d, want 9999", cfg.Port)
	}
	if cfg.Host != "127.0.0.1" {
		t.Errorf("Host = %q, want 127.0.0.1", cfg.Host)
	}
	if cfg.DefaultModel != "deepseek/deepseek-chat" {
		t.Errorf("Model = %q, want deepseek/deepseek-chat", cfg.DefaultModel)
	}
	if cfg.Temperature != 0.7 {
		t.Errorf("Temperature = %f, want 0.7", cfg.Temperature)
	}
}

func TestLoadConfigFallbackDefaults(t *testing.T) {
	// Load from non-existent file → should return defaults
	cfg := LoadConfig(filepath.Join(t.TempDir(), "nonexistent.json"))

	if cfg.Port != 4173 {
		t.Errorf("Fallback Port = %d, want 4173", cfg.Port)
	}
	if cfg.DefaultModel != "google/gemini-2.5-flash" {
		t.Errorf("Fallback Model = %q, want google/gemini-2.5-flash", cfg.DefaultModel)
	}
}

func TestLoadConfigEnvOverrides(t *testing.T) {
	t.Setenv("PORT", "8080")
	t.Setenv("HOST", "localhost")
	t.Setenv("DATA_DIR", "/custom/data")
	t.Setenv("NOVEL_MODEL", "openai/gpt-4o")

	cfg := LoadConfig(filepath.Join(t.TempDir(), "nonexistent.json"))

	if cfg.Port != 8080 {
		t.Errorf("Env Port = %d, want 8080", cfg.Port)
	}
	if cfg.Host != "localhost" {
		t.Errorf("Env Host = %q, want localhost", cfg.Host)
	}
	if cfg.DataDir != "/custom/data" {
		t.Errorf("Env DataDir = %q, want /custom/data", cfg.DataDir)
	}
	if cfg.DefaultModel != "openai/gpt-4o" {
		t.Errorf("Env Model = %q, want openai/gpt-4o", cfg.DefaultModel)
	}
}

func TestProviderGetter(t *testing.T) {
	cfg := DefaultConfig()
	cfg.Provider = "9router"
	if got := cfg.GetProvider(); got != "9router" {
		t.Errorf("GetProvider() = %q, want 9router", got)
	}
}

func TestSaveConfig(t *testing.T) {
	dir := t.TempDir()
	cfgPath := filepath.Join(dir, "sub", "config.json")

	cfg := DefaultConfig()
	cfg.Port = 5555

	if err := cfg.Save(cfgPath); err != nil {
		t.Fatalf("Save failed: %v", err)
	}

	// Verify file exists and contains correct data
	data, err := os.ReadFile(cfgPath)
	if err != nil {
		t.Fatalf("Cannot read saved config: %v", err)
	}

	var loaded AppConfig
	if err := json.Unmarshal(data, &loaded); err != nil {
		t.Fatalf("Cannot parse saved config: %v", err)
	}
	if loaded.Port != 5555 {
		t.Errorf("Saved Port = %d, want 5555", loaded.Port)
	}
}
