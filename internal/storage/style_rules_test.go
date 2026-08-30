package storage

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRenderStyleRules(t *testing.T) {
	yml := "# comment\npunctuation:\n- text: Use em-dash.\n- text: 'End marker: use (x) in the last block.'\nnaturalness:\n- text: 'Filter words: remove a, b,\n    c, d.'\n"
	out := renderStyleRules(yml)

	if !strings.Contains(out, "[punctuation]") || !strings.Contains(out, "[naturalness]") {
		t.Errorf("section headers missing: %s", out)
	}
	if !strings.Contains(out, "- Use em-dash.") {
		t.Errorf("plain item missing: %s", out)
	}
	if !strings.Contains(out, "- End marker: use (x) in the last block.") {
		t.Errorf("quoted item with colon not unwrapped: %s", out)
	}
	if !strings.Contains(out, "- Filter words: remove a, b, c, d.") {
		t.Errorf("multiline continuation not joined: %s", out)
	}
}

func TestParseGlossaryYAML(t *testing.T) {
	yml := "# header\n\nterms:\n- source: \u66f9\u661f\n  thai: \u0e40\u0e09\u0e32\u0e0b\u0e34\u0e07\n  category: \u0e15\u0e31\u0e27\u0e25\u0e30\u0e04\u0e23\n  priority: 1\n  lock: locked\n  explanation: ''\n  notes: protagonist\n- source: '\u5927\u5ac2'\n  thai: '\u0e1e\u0e35\u0e48\u0e2a\u0e30\u0e43\u0e20\u0e49'\n  category: general\n  notes: sister-in-law\n"
	items := parseGlossaryYAML(yml)

	if len(items) != 2 {
		t.Fatalf("expected 2 items, got %d: %+v", len(items), items)
	}
	if items[0].Term != "\u66f9\u661f" || items[0].Target != "\u0e40\u0e09\u0e32\u0e0b\u0e34\u0e07" {
		t.Errorf("item 0 wrong: %+v", items[0])
	}
	if items[0].Notes != "protagonist" {
		t.Errorf("empty explanation should not pollute notes: %+v", items[0])
	}
	if items[1].Term != "\u5927\u5ac2" || items[1].Target != "\u0e1e\u0e35\u0e48\u0e2a\u0e30\u0e43\u0e20\u0e49" {
		t.Errorf("quoted item not unwrapped: %+v", items[1])
	}
}

func TestGetGlossary_MergesYAML(t *testing.T) {
	dir := t.TempDir()
	slug := "test-novel"
	gdir := filepath.Join(dir, slug, "glossary")
	_ = os.MkdirAll(gdir, 0755)

	// curated json wins on conflict
	_ = os.WriteFile(filepath.Join(gdir, "glossary.json"),
		[]byte(`[{"term":"\u66f9\u661f","target":"JSON-WINS","category":"character"}]`), 0644)
	_ = os.WriteFile(filepath.Join(gdir, "glossary.yml"),
		[]byte("terms:\n- source: \u66f9\u661f\n  thai: YML-LOSES\n- source: \u5927\u5ac2\n  thai: \u0e1e\u0e35\u0e48\u0e2a\u0e30\u0e43\u0e20\u0e49\n"), 0644)

	s := &Store{DataDir: dir}
	g, err := s.GetGlossary(slug)
	if err != nil {
		t.Fatal(err)
	}
	if len(g.Terms) != 2 {
		t.Fatalf("expected 2 merged terms, got %d: %+v", len(g.Terms), g.Terms)
	}
	if g.Terms[0].Target != "JSON-WINS" {
		t.Errorf("glossary.json should win on conflict: %+v", g.Terms[0])
	}
	if g.Terms[1].Term != "\u5927\u5ac2" {
		t.Errorf("yml-only term missing: %+v", g.Terms[1])
	}
}

func TestGetStyleRules(t *testing.T) {
	dir := t.TempDir()
	slug := "test-novel"
	_ = os.MkdirAll(filepath.Join(dir, slug), 0755)
	_ = os.WriteFile(filepath.Join(dir, slug, "style_rules.yml"),
		[]byte("punctuation:\n- text: Use em-dash.\n"), 0644)

	s := &Store{DataDir: dir}
	out, err := s.GetStyleRules(slug)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, "Use em-dash.") {
		t.Errorf("style rules not rendered: %q", out)
	}

	// missing file -> empty, no error
	out, err = s.GetStyleRules("no-such-novel")
	if err != nil || out != "" {
		t.Errorf("missing style_rules.yml should return empty: %q, %v", out, err)
	}
}

func TestGetGlossary_YAMLOnlyAndCorruptJSON(t *testing.T) {
	dir := t.TempDir()
	slug := "yaml-only"
	gdir := filepath.Join(dir, slug, "glossary")
	if err := os.MkdirAll(gdir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(gdir, "glossary.yml"),
		[]byte("terms:\n- source: \u66f9\u661f\n  thai: \u0e40\u0e09\u0e32\u0e0b\u0e34\u0e07\n"), 0644); err != nil {
		t.Fatal(err)
	}
	s := NewStore(dir)
	g, err := s.GetGlossary(slug)
	if err != nil {
		t.Fatal(err)
	}
	if len(g.Terms) != 1 || g.Terms[0].Target == "" {
		t.Fatalf("YAML-only glossary was not loaded: %+v", g.Terms)
	}

	if err := os.WriteFile(filepath.Join(gdir, "glossary.json"), []byte(`{"terms":`), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := s.GetGlossary(slug); err == nil {
		t.Fatal("corrupt glossary JSON should return an error")
	}
}

func TestGetStyleRulesReadErrorIsNotHidden(t *testing.T) {
	dir := t.TempDir()
	slug := "bad-style"
	path := filepath.Join(dir, slug, "style_rules.yml")
	if err := os.MkdirAll(path, 0755); err != nil {
		t.Fatal(err)
	}
	s := NewStore(dir)
	if _, err := s.GetStyleRules(slug); err == nil {
		t.Fatal("style_rules read error should be returned")
	}
}

func TestGetGlossaryReturnsErrorWhenYAMLIsUnreadable(t *testing.T) {
	dir := t.TempDir()
	gdir := filepath.Join(dir, "yaml-error", "glossary")
	if err := os.MkdirAll(filepath.Join(gdir, "glossary.yml"), 0755); err != nil {
		t.Fatal(err)
	}
	if _, err := NewStore(dir).GetGlossary("yaml-error"); err == nil {
		t.Fatal("expected unreadable glossary.yml to return an error")
	}
}
