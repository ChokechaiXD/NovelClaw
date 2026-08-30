package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestProviderProfilesStayIndependent(t *testing.T) {
	cfg := DefaultConfig()
	cfg.ConfigPath = filepath.Join(t.TempDir(), "config.json")
	openRouterKey := "or-secret"
	if err := cfg.ConfigureProvider("openrouter", "", &openRouterKey, "or-model", "", true); err != nil {
		t.Fatal(err)
	}
	geminiKey := "gem-secret"
	if err := cfg.ConfigureProvider("gemini", "", &geminiKey, "gemini-model", "", true); err != nil {
		t.Fatal(err)
	}
	if got := cfg.ActiveProvider(); got.ID != "gemini" || got.APIKey != geminiKey || got.Model != "gemini-model" {
		t.Fatalf("wrong active Gemini profile: %+v", got)
	}
	or := cfg.ProviderRuntime("openrouter")
	if or.APIKey != openRouterKey || or.Model != "or-model" {
		t.Fatalf("OpenRouter profile was overwritten: %+v", or)
	}
}
func TestProviderProfilesPersistAcrossReload(t *testing.T) {
	path := filepath.Join(t.TempDir(), "config.json")
	cfg := DefaultConfig()
	cfg.ConfigPath = path
	key := "persist-me"
	if err := cfg.ConfigureProvider("openrouter", "", &key, "provider/model", "", true); err != nil {
		t.Fatal(err)
	}
	reloaded := LoadConfig(path)
	got := reloaded.ActiveProvider()
	if got.ID != "openrouter" || got.APIKey != key || got.Model != "provider/model" {
		t.Fatalf("profile did not survive reload: %+v", got)
	}
}

func TestCustomOriginChangeDropsImplicitSecret(t *testing.T) {
	cfg := DefaultConfig()
	cfg.ConfigPath = filepath.Join(t.TempDir(), "config.json")
	key := "secret"
	if err := cfg.ConfigureProvider("custom", "https://one.example/v1", &key, "m", "", true); err != nil {
		t.Fatal(err)
	}
	if err := cfg.ConfigureProvider("custom", "https://two.example/v1", nil, "m", "", true); err != nil {
		t.Fatal(err)
	}
	if got := cfg.ActiveProvider().APIKey; got != "" {
		t.Fatalf("secret crossed provider origin: %q", got)
	}
}

func TestRuntimeProviderOverrideUsesRegistryWithoutPersisting(t *testing.T) {
	cfg := DefaultConfig()
	cfg.ConfigPath = filepath.Join(t.TempDir(), "config.json")
	cfg.ApplyRuntimeProviderOverride("https://openrouter.ai/api/v1", "runtime-key", "vendor/model")

	active := cfg.ActiveProvider()
	if active.ID != "openrouter" || active.APIKey != "runtime-key" || active.Model != "vendor/model" {
		t.Fatalf("runtime provider mismatch: %#v", active)
	}
	if _, err := os.Stat(cfg.ConfigPath); !os.IsNotExist(err) {
		t.Fatalf("runtime override unexpectedly persisted config: err=%v", err)
	}
}
