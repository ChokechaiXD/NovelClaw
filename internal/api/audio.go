package api

import (
	"bytes"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type SpeechRequest struct {
	Text  string  `json:"text"`
	Voice string  `json:"voice"` // e.g. "edge-tts/th-TH-NiwatNeural"
	Speed float64 `json:"speed,omitempty"`
}

// GenerateSpeech generates or returns cached studio-quality neural audio for text
func (h *APIHandler) GenerateSpeech(w http.ResponseWriter, r *http.Request) {
	var req SpeechRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		WriteError(w, http.StatusBadRequest, "Invalid payload")
		return
	}

	text := strings.TrimSpace(req.Text)
	if text == "" {
		WriteError(w, http.StatusBadRequest, "Text is required")
		return
	}

	voice := req.Voice
	if voice == "" {
		voice = "edge-tts/th-TH-NiwatNeural"
	}

	// Cache check based on MD5 hash of (voice + text)
	cacheKey := fmt.Sprintf("%s_%s", voice, text)
	hash := md5.Sum([]byte(cacheKey))
	hashStr := hex.EncodeToString(hash[:])

	cacheDir := filepath.Join(h.cfg.DataDir, ".cache", "audio")
	_ = os.MkdirAll(cacheDir, 0755)
	cacheFile := filepath.Join(cacheDir, hashStr+".mp3")

	if info, err := os.Stat(cacheFile); err == nil && info.Size() > 0 {
		audioData, err := os.ReadFile(cacheFile)
		if err == nil {
			w.Header().Set("Content-Type", "audio/mp3")
			w.Header().Set("X-Cache", "HIT")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write(audioData)
			return
		}
	}

	// Call 9Router /v1/audio/speech
	routerURL := strings.TrimRight(h.cfg.GetRouterURL(), "/")
	if !strings.HasSuffix(routerURL, "/v1") && !strings.Contains(routerURL, "/audio/speech") {
		routerURL += "/v1"
	}
	if !strings.HasSuffix(routerURL, "/audio/speech") {
		routerURL += "/audio/speech"
	}

	payload := map[string]interface{}{
		"model": voice,
		"input": text,
	}
	jsonData, _ := json.Marshal(payload)

	httpReq, err := http.NewRequestWithContext(r.Context(), "POST", routerURL, bytes.NewReader(jsonData))
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}

	httpReq.Header.Set("Content-Type", "application/json")
	if apiKey := h.cfg.GetAPIKey(); apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+apiKey)
	}

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		WriteError(w, http.StatusBadGateway, fmt.Sprintf("TTS gateway error: %v", err))
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<10))
		WriteError(w, resp.StatusCode, fmt.Sprintf("TTS upstream error (HTTP %d): %s", resp.StatusCode, string(body)))
		return
	}

	audioData, err := io.ReadAll(io.LimitReader(resp.Body, 50<<20))
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}

	// Save to disk cache
	_ = os.WriteFile(cacheFile, audioData, 0644)

	w.Header().Set("Content-Type", "audio/mp3")
	w.Header().Set("X-Cache", "MISS")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(audioData)
}
