package scraper

import (
	"strings"
	"testing"
)

// validateDial re-checks the concrete dial target so a DNS rebinding attack
// cannot slip a private address past URL validation.
func TestValidateDial(t *testing.T) {
	blocked := []string{
		"127.0.0.1:8080",
		"[::1]:8080",
		"10.1.2.3:443",
		"192.168.0.10:80",
		"172.16.5.5:80",
		"169.254.169.254:80", // cloud metadata endpoint
		"0.0.0.0:80",
		"example.invalid:80", // non-IP dial target (resolver bypass attempt)
	}
	for _, addr := range blocked {
		if err := validateDial("tcp", addr, nil); err == nil {
			t.Errorf("validateDial(%q) = nil; want error (should be blocked)", addr)
		} else if !strings.Contains(err.Error(), "blocked") {
			t.Errorf("validateDial(%q) error = %v; want an SSRF-block error", addr, err)
		}
	}

	allowed := []string{
		"93.184.216.34:443",
		"[2606:2800:220:1:248:1893:25c8:1946]:443",
	}
	for _, addr := range allowed {
		if err := validateDial("tcp", addr, nil); err != nil {
			t.Errorf("validateDial(%q) = %v; want nil (public IP must dial)", addr, err)
		}
	}
}
