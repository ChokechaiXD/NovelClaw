package scraper

import (
	"strings"
	"testing"
)

func TestValidatePublicURL(t *testing.T) {
	blocked := []string{
		"file:///C:/Users/x/config.json",
		"ftp://example.com/file",
		"http://localhost:4173/api",
		"http://127.0.0.1:20128/v1",
		"http://[::1]/x",
		"http://10.0.0.5/internal",
		"http://192.168.1.1/router",
		"http://172.16.0.9/admin",
		"http://169.254.169.254/latest/meta-data/", // cloud metadata
		"http://0.0.0.0/x",
		"not a url at all",
		"",
	}
	for _, u := range blocked {
		if err := validatePublicURL(u); err == nil {
			t.Errorf("validatePublicURL(%q) = nil; want error (should be blocked)", u)
		}
	}

	allowed := []string{
		"https://www.69shu.com/txt/30190",
		"http://example.com/chapter/1",
		"https://novel.example.org/book/123",
	}
	for _, u := range allowed {
		if err := validatePublicURL(u); err != nil {
			// DNS may fail in sandboxed CI; only fail on scheme/host logic errors.
			if strings.Contains(err.Error(), "scheme") || strings.Contains(err.Error(), "private") || strings.Contains(err.Error(), "no host") {
				t.Errorf("validatePublicURL(%q) unexpectedly blocked: %v", u, err)
			}
		}
	}
}
