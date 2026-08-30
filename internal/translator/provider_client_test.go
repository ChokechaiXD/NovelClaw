package translator

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"novelclaw/internal/config"
)

func testProviderConfig(t *testing.T, id, baseURL, key, model, protocol string) *config.AppConfig {
	t.Helper()
	cfg := config.DefaultConfig()
	cfg.ConfigPath = filepath.Join(t.TempDir(), "config.json")
	if err := cfg.ConfigureProvider(id, baseURL, &key, model, protocol, true); err != nil {
		t.Fatal(err)
	}
	return cfg
}

func TestDeepSeekUsesRootChatCompletions(t *testing.T) {
	var gotPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"choices": []interface{}{map[string]interface{}{"message": map[string]string{"content": "แปลแล้ว"}}}})
	}))
	defer server.Close()
	cfg := testProviderConfig(t, "deepseek", server.URL, "key", "deepseek-v4-flash", "")
	out, err := NewClient(cfg).Complete(context.Background(), "sys", "user", "", 0.3)
	if err != nil {
		t.Fatal(err)
	}
	if gotPath != "/chat/completions" {
		t.Fatalf("path=%q", gotPath)
	}
	if out != "แปลแล้ว" {
		t.Fatalf("out=%q", out)
	}
}
func TestAnthropicUsesNativeMessagesAuth(t *testing.T) {
	var gotPath, gotKey, gotBearer string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath, gotKey, gotBearer = r.URL.Path, r.Header.Get("x-api-key"), r.Header.Get("Authorization")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"content": []interface{}{map[string]string{"type": "text", "text": "ข้อความ"}}})
	}))
	defer server.Close()
	cfg := testProviderConfig(t, "anthropic", server.URL, "anth-key", "claude-test", "")
	out, err := NewClient(cfg).Complete(context.Background(), "sys", "user", "", 0.3)
	if err != nil {
		t.Fatal(err)
	}
	if gotPath != "/messages" || gotKey != "anth-key" || gotBearer != "" {
		t.Fatalf("path=%q key=%q bearer=%q", gotPath, gotKey, gotBearer)
	}
	if out != "ข้อความ" {
		t.Fatalf("out=%q", out)
	}
}

func TestOpenCodeFreeDeepSeekUsesChatEndpoint(t *testing.T) {
	var gotPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"choices": []interface{}{map[string]interface{}{"message": map[string]string{"content": "ok"}}}})
	}))
	defer server.Close()
	cfg := testProviderConfig(t, "opencode-zen", server.URL, "zen-key", "deepseek-v4-flash-free", "")
	if _, err := NewClient(cfg).Complete(context.Background(), "sys", "user", "", 0.3); err != nil {
		t.Fatal(err)
	}
	if gotPath != "/chat/completions" {
		t.Fatalf("path=%q", gotPath)
	}
}
func TestFetchModelsUsesProviderModelsEndpoint(t *testing.T) {
	var gotPath string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"data": []interface{}{map[string]string{"id": "z-model"}, map[string]string{"id": "a-model"}}})
	}))
	defer server.Close()
	cfg := testProviderConfig(t, "openrouter", server.URL, "key", "a-model", "")
	models, err := NewClient(cfg).FetchModels(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if gotPath != "/models" {
		t.Fatalf("path=%q", gotPath)
	}
	if len(models) != 2 || models[0] != "a-model" || models[1] != "z-model" {
		t.Fatalf("models=%v", models)
	}
}

func TestOpenCodeQwenUsesMessagesEndpoint(t *testing.T) {
	var gotPath, gotBearer string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		gotBearer = r.Header.Get("Authorization")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"content": []interface{}{map[string]string{"type": "text", "text": "ok"}},
		})
	}))
	defer server.Close()
	cfg := testProviderConfig(t, "opencode-zen", server.URL, "zen-key", "qwen3.7-plus", "")
	if _, err := NewClient(cfg).Complete(context.Background(), "sys", "user", "", 0.3); err != nil {
		t.Fatal(err)
	}
	if gotPath != "/messages" || gotBearer != "Bearer zen-key" {
		t.Fatalf("path=%q bearer=%q", gotPath, gotBearer)
	}
}

func TestOpenCodeModelsHideUnsupportedGemini(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"data": []interface{}{
				map[string]string{"id": "gemini-3.6-flash"},
				map[string]string{"id": "deepseek-v4-flash-free"},
				map[string]string{"id": "claude-sonnet-5"},
			},
		})
	}))
	defer server.Close()
	cfg := testProviderConfig(t, "opencode-zen", server.URL, "zen-key", "deepseek-v4-flash-free", "")
	models, err := NewClient(cfg).FetchModels(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(models) != 2 {
		t.Fatalf("models=%v", models)
	}
	for _, model := range models {
		if model == "gemini-3.6-flash" {
			t.Fatalf("unsupported Zen Gemini leaked into model list: %v", models)
		}
	}
}

func TestProviderSnapshotDoesNotFollowActiveProviderSwitch(t *testing.T) {
	var hitsA, hitsB int
	serverA := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hitsA++
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"choices": []interface{}{map[string]interface{}{"message": map[string]string{"content": "จาก A"}}},
		})
	}))
	defer serverA.Close()
	serverB := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hitsB++
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"choices": []interface{}{map[string]interface{}{"message": map[string]string{"content": "จาก B"}}},
		})
	}))
	defer serverB.Close()
	cfg := config.DefaultConfig()
	cfg.ConfigPath = filepath.Join(t.TempDir(), "config.json")
	keyA, keyB := "key-a", "key-b"
	if err := cfg.ConfigureProvider("deepseek", serverA.URL, &keyA, "model-a", "", true); err != nil {
		t.Fatal(err)
	}
	snapshot := cfg.ProviderRuntime("deepseek")
	if err := cfg.ConfigureProvider("openrouter", serverB.URL, &keyB, "model-b", "", true); err != nil {
		t.Fatal(err)
	}

	out, usedModel, err := NewClient(cfg).CompleteWithFallbackForProvider(
		context.Background(), snapshot, "sys", "user", []string{"model-a"}, 0.3,
	)
	if err != nil {
		t.Fatal(err)
	}
	if out != "จาก A" || usedModel != "model-a" {
		t.Fatalf("out=%q model=%q", out, usedModel)
	}
	if hitsA != 1 || hitsB != 0 {
		t.Fatalf("snapshot drifted after provider switch: hitsA=%d hitsB=%d", hitsA, hitsB)
	}
}

func TestFetchModelCatalogMarksFreeModels(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"data": []interface{}{
				map[string]interface{}{"id": "vendor/paid", "pricing": map[string]string{"prompt": "0.1", "completion": "0.2"}},
				map[string]interface{}{"id": "vendor/zero", "pricing": map[string]string{"prompt": "0", "completion": "0"}},
				map[string]string{"id": "vendor/model:free"},
				map[string]string{"id": "openrouter/free"},
			},
		})
	}))
	defer server.Close()
	cfg := testProviderConfig(t, "openrouter", server.URL, "key", "vendor/paid", "")
	catalog, err := NewClient(cfg).FetchModelCatalogFor(context.Background(), "openrouter")
	if err != nil {
		t.Fatal(err)
	}
	free := map[string]bool{}
	for _, model := range catalog {
		free[model.ID] = model.Free
	}
	if free["vendor/paid"] {
		t.Fatal("paid model marked free")
	}
	for _, id := range []string{"vendor/zero", "vendor/model:free", "openrouter/free"} {
		if !free[id] {
			t.Fatalf("expected %s to be free: %#v", id, catalog)
		}
	}
}

func TestOpenCodeCatalogMarksFreeModels(t *testing.T) {
	if !providerModelIsFree("opencode-zen", "big-pickle", "", "") {
		t.Fatal("big-pickle should be treated as a Zen free model")
	}
	if !providerModelIsFree("opencode-zen", "mimo-v2.5-free", "", "") {
		t.Fatal("Zen *-free model should be free")
	}
	if providerModelIsFree("opencode-zen", "deepseek-v4-pro", "", "") {
		t.Fatal("paid Zen model marked free")
	}
}
