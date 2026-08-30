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

var ttsHTTPClient = &http.Client{Timeout: 30 * time.Second}

// GenerateSpeech generates or returns cached studio-quality neural audio for text
func (h *APIHandler) GenerateSpeech(w http.ResponseWriter, r *http.Request) {
	var req SpeechRequest
	if err := decodeJSONBody(w, r, &req, bodySpeech); err != nil {
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
	if err := os.MkdirAll(cacheDir, 0755); err != nil {
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("create TTS cache: %v", err))
		return
	}
	cacheFile := filepath.Join(cacheDir, hashStr+".mp3")

	if f, err := os.Open(cacheFile); err == nil {
		if info, statErr := f.Stat(); statErr == nil && info.Size() > 0 {
			defer f.Close()
			w.Header().Set("Content-Type", "audio/mpeg")
			w.Header().Set("X-Cache", "HIT")
			http.ServeContent(w, r, cacheFile, info.ModTime(), f)
			return
		}
		_ = f.Close()
	} else if !os.IsNotExist(err) {
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("read TTS cache: %v", err))
		return
	}

	// TTS is intentionally decoupled from the active LLM provider. Switching
	// translation to OpenRouter/Gemini/Claude must not redirect Edge-TTS calls
	// away from the local 9Router gateway.
	ttsProvider := h.cfg.ProviderRuntime("9router")
	routerURL := strings.TrimRight(ttsProvider.BaseURL, "/")
	if routerURL == "" {
		WriteError(w, http.StatusServiceUnavailable, "TTS gateway is not configured")
		return
	}
	if !strings.HasSuffix(routerURL, "/audio/speech") {
		routerURL += "/audio/speech"
	}

	payload := map[string]interface{}{
		"model": voice,
		"input": text,
	}
	jsonData, err := json.Marshal(payload)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, fmt.Sprintf("encode TTS request: %v", err))
		return
	}

	httpReq, err := http.NewRequestWithContext(r.Context(), "POST", routerURL, bytes.NewReader(jsonData))
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}

	httpReq.Header.Set("Content-Type", "application/json")
	if ttsProvider.APIKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+ttsProvider.APIKey)
	}

	resp, err := ttsHTTPClient.Do(httpReq)
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

	// Stream upstream audio to a temporary file instead of buffering up to
	// 50 MB in RAM. Rename only after a complete read so cache files are atomic.
	tmp, err := os.CreateTemp(cacheDir, "tts-*.tmp")
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	const maxAudioBytes int64 = 50 << 20
	written, copyErr := io.Copy(tmp, io.LimitReader(resp.Body, maxAudioBytes+1))
	closeErr := tmp.Close()
	if copyErr != nil || closeErr != nil {
		WriteError(w, http.StatusBadGateway, "Failed to cache TTS audio")
		return
	}
	if written > maxAudioBytes {
		WriteError(w, http.StatusBadGateway, "TTS response exceeded 50 MB")
		return
	}
	if err := os.Rename(tmpName, cacheFile); err != nil {
		// Concurrent requests for the same paragraph may race to populate the
		// same cache key. If another request already won, reuse its file.
		if info, statErr := os.Stat(cacheFile); statErr != nil || info.Size() == 0 {
			WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}
	}

	f, err := os.Open(cacheFile)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	w.Header().Set("Content-Type", "audio/mpeg")
	w.Header().Set("X-Cache", "MISS")
	http.ServeContent(w, r, cacheFile, info.ModTime(), f)
}
