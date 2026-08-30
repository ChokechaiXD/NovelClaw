package scraper

import (
	"testing"
)

func TestExtractChapterNumber(t *testing.T) {
	tests := []struct {
		input    string
		expected int
	}{
		{"第1章 冰封纪元开启", 1},
		{"第123章 决战", 123},
		{"第0045章 森林探险", 45},
		{"Chapter 88: The Beginning", 88},
		{"ตอนที่ 5 วันแรก", 5},
		{"https://www.69shu.com/txt/30190/20392019", 0},
	}

	for _, tt := range tests {
		got := extractChapterNumber(tt.input)
		if got != tt.expected {
			t.Errorf("extractChapterNumber(%q) = %d; want %d", tt.input, got, tt.expected)
		}
	}
}

func TestIs69ShuJunk(t *testing.T) {
	tests := []struct {
		input    string
		expected bool
	}{
		{"", true},
		{"   ", true},
		{"(本章完)", true},
		{"請記住本書首發域名：69shu.com", true},
		{"曹星低下头去继续看平板。", false},
	}

	for _, tt := range tests {
		got := is69ShuJunk(tt.input)
		if got != tt.expected {
			t.Errorf("is69ShuJunk(%q) = %v; want %v", tt.input, got, tt.expected)
		}
	}
}

func TestValidateHTMLContentType(t *testing.T) {
	allowed := []string{"", "text/html; charset=utf-8", "text/plain", "application/xhtml+xml", "application/xml"}
	for _, contentType := range allowed {
		if err := validateHTMLContentType(contentType); err != nil {
			t.Fatalf("expected %q to be allowed: %v", contentType, err)
		}
	}
	blocked := []string{"application/json", "application/pdf", "application/octet-stream", "image/png", "video/mp4"}
	for _, contentType := range blocked {
		if err := validateHTMLContentType(contentType); err == nil {
			t.Fatalf("expected %q to be rejected", contentType)
		}
	}
}
