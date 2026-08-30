package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestDefaultConfig(t *testing.T) {
	cfg := DefaultConfig()

	if cfg.Port != 4890 {
		t.Errorf("Default Port = %d, want 4890", cfg.Port)
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

	if cfg.Port != 4890 {
		t.Errorf("Fallback Port = %d, want 4890", cfg.Port)
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

func TestSaveConfigWritesRecoveryBackup(t *testing.T) {
	dir := t.TempDir()
	cfgPath := filepath.Join(dir, "config.json")
	cfg := DefaultConfig()
	cfg.ConfigPath = cfgPath
	cfg.Port = 6123
	if err := cfg.Save(""); err != nil {
		t.Fatal(err)
	}
	backup, err := os.ReadFile(cfgPath + ".bak")
	if err != nil {
		t.Fatalf("backup missing: %v", err)
	}
	var recovered AppConfig
	if err := json.Unmarshal(backup, &recovered); err != nil {
		t.Fatalf("backup invalid: %v", err)
	}
	if recovered.Port != 6123 {
		t.Fatalf("backup port=%d", recovered.Port)
	}

	cfg.Port = 6124
	if err := cfg.Save(""); err != nil {
		t.Fatal(err)
	}
	backup, err = os.ReadFile(cfgPath + ".bak")
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(backup, &recovered); err != nil || recovered.Port != 6124 {
		t.Fatalf("backup did not refresh: port=%d err=%v", recovered.Port, err)
	}
}

func TestLoadConfigRecoversFromBackup(t *testing.T) {
	dir := t.TempDir()
	cfgPath := filepath.Join(dir, "config.json")
	cfg := DefaultConfig()
	cfg.ConfigPath = cfgPath
	cfg.Provider = "9router"
	cfg.Port = 7331
	if err := cfg.Save(""); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(cfgPath, []byte("{broken"), 0600); err != nil {
		t.Fatal(err)
	}
	recovered := LoadConfig(cfgPath)
	if recovered.Port != 7331 {
		t.Fatalf("recovered port=%d", recovered.Port)
	}
	if recovered.ConfigPath != cfgPath {
		t.Fatalf("config path=%q", recovered.ConfigPath)
	}
}

func TestLoadConfigPrefersPersistedActiveProviderProfile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "config.json")
	data := []byte(`{
  "provider":"custom",
  "providers":{"custom":{"baseUrl":"http://127.0.0.1:9940/v1","model":"mock-intel","protocol":"openai-chat"}},
  "dataDir":"` + filepath.ToSlash(filepath.Join(dir, "data")) + `"
}`)
	if err := os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	cfg := LoadConfig(path)
	provider := cfg.ActiveProvider()
	if provider.ID != "custom" || provider.BaseURL != "http://127.0.0.1:9940/v1" || provider.Model != "mock-intel" {
		t.Fatalf("persisted profile lost to legacy defaults: %+v", provider)
	}
	if cfg.RouterURL != provider.BaseURL || cfg.DefaultModel != provider.Model {
		t.Fatalf("legacy mirror not synced: router=%q model=%q", cfg.RouterURL, cfg.DefaultModel)
	}
}
