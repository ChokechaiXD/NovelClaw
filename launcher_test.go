package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestBrowserURL(t *testing.T) {
	if got := browserURL("0.0.0.0", 4890); got != "http://127.0.0.1:4890" {
		t.Fatalf("browserURL=%q", got)
	}
	if got := browserURL("::", 4890); got != "http://127.0.0.1:4890" {
		t.Fatalf("browserURL IPv6 wildcard=%q", got)
	}
}

func TestNovelClawRespondingHealth(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/health" {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"app":"NovelClaw","status":"ok"}`))
			return
		}
		http.NotFound(w, r)
	}))
	defer srv.Close()
	if !novelClawResponding(srv.URL) {
		t.Fatal("expected health endpoint to identify NovelClaw")
	}
}

func TestNovelClawRespondingLegacyFallback(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/health" {
			http.NotFound(w, r)
			return
		}
		_, _ = w.Write([]byte(`<title>NovelClaw</title><div id="novel-grid"></div>`))
	}))
	defer srv.Close()
	if !novelClawResponding(srv.URL) {
		t.Fatal("expected legacy UI markers to identify NovelClaw")
	}
}

func TestNovelClawRespondingRejectsOtherService(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("other service"))
	}))
	defer srv.Close()
	if novelClawResponding(srv.URL) {
		t.Fatal("unexpectedly identified another service as NovelClaw")
	}
}
