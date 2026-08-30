package api

import (
	"encoding/json"
	"math"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestWriteJSONMarshalFailureReturnsValid500(t *testing.T) {
	recorder := httptest.NewRecorder()
	WriteJSON(recorder, http.StatusOK, map[string]float64{"bad": math.Inf(1)})
	if recorder.Code != http.StatusInternalServerError {
		t.Fatalf("status=%d", recorder.Code)
	}
	var body map[string]string
	if err := json.Unmarshal(recorder.Body.Bytes(), &body); err != nil {
		t.Fatalf("invalid fallback JSON: %v body=%q", err, recorder.Body.String())
	}
	if body["error"] == "" {
		t.Fatalf("missing error body: %v", body)
	}
}

func TestPositiveQueryIntRejectsInvalidValues(t *testing.T) {
	for _, raw := range []string{"abc", "0", "-4"} {
		req := httptest.NewRequest(http.MethodGet, "/?start="+raw, nil)
		if _, err := positiveQueryInt(req, "start", 1); err == nil {
			t.Fatalf("start=%q should fail", raw)
		}
	}
}

func TestPositiveQueryIntUsesDefaultWhenMissing(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	value, err := positiveQueryInt(req, "start", 7)
	if err != nil || value != 7 {
		t.Fatalf("value=%d err=%v", value, err)
	}
}
