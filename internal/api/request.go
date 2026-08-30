package api

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
)

const (
	bodyTiny   int64 = 64 << 10  // config, bookmark, job commands
	bodySmall  int64 = 1 << 20   // metadata, glossary, memory
	bodyImport int64 = 16 << 20  // manual-paste novel content
	bodySpeech int64 = 256 << 10 // one TTS paragraph/request
)

func positiveQueryInt(r *http.Request, name string, defaultValue int) (int, error) {
	raw := r.URL.Query().Get(name)
	if raw == "" {
		return defaultValue, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value <= 0 {
		return 0, fmt.Errorf("%s must be a positive integer", name)
	}
	return value, nil
}

func decodeJSONBody(w http.ResponseWriter, r *http.Request, dst any, maxBytes int64) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxBytes)
	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(dst); err != nil {
		return err
	}
	var extra any
	if err := dec.Decode(&extra); err != io.EOF {
		return fmt.Errorf("request body must contain one JSON value")
	}
	return nil
}
