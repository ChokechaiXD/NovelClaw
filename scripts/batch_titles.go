//go:build ignore

// Batch-translate chapter titles (source → Thai) for already-translated
// chapters, using the original title kept in the paired .cn.json file.
// Run: go run scripts/batch_titles.go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"novelclaw/internal/config"
	"novelclaw/internal/translator"
)

var autoRe = regexp.MustCompile(`^ตอนที่\s*\d+$`)

func cleanTitle(t string) string {
	for {
		i := strings.Index(t, ">>")
		if i == -1 {
			return strings.TrimSpace(t)
		}
		t = t[i+2:]
	}
}

func main() {
	cfg := config.LoadConfig("config.json")
	client := translator.NewClient(cfg)

	dir := "novels/global-descent/chapters"
	paths, _ := filepath.Glob(filepath.Join(dir, "*.th.json"))
	sort.Strings(paths)

	type item struct {
		thPath string
		no     int
		src    string
		doc    map[string]any
		have   string // existing real Thai title (kept as-is)
	}
	var items []item
	for _, p := range paths {
		base := strings.TrimSuffix(filepath.Base(p), ".th.json")
		cnData, err := os.ReadFile(filepath.Join(dir, base+".cn.json"))
		if err != nil {
			continue
		}
		var cn map[string]any
		if json.Unmarshal(cnData, &cn) != nil {
			continue
		}
		cnTitle, _ := cn["title"].(map[string]any)
		src, _ := cnTitle["source"].(string)
		if strings.TrimSpace(src) == "" {
			continue
		}
		src = cleanTitle(src)

		thData, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		var doc map[string]any
		if json.Unmarshal(thData, &doc) != nil {
			continue
		}
		title, _ := doc["title"].(map[string]any)
		if title == nil {
			title = map[string]any{}
			doc["title"] = title
		}
		have, _ := title["translated"].(string)
		have = strings.TrimSpace(have)

		no := 0
		fmt.Sscanf(base, "%04d", &no)
		items = append(items, item{p, no, src, doc, have})
	}
	fmt.Printf("th.json with source available: %d\n", len(items))

	already := 0
	keep := make([]bool, len(items))
	for i, it := range items {
		if it.have != "" && !autoRe.MatchString(it.have) {
			keep[i] = true
		}
	}
	if already > 0 {
		fmt.Printf("already-real Thai titles kept: %d\n", already)
	}
	var toTranslate []item
	for i, it := range items {
		if !keep[i] {
			toTranslate = append(toTranslate, it)
		}
	}
	fmt.Printf("titles to translate: %d\n", len(toTranslate))

	if len(toTranslate) > 0 {
		const chunkSize = 30
		written := 0
		for start := 0; start < len(toTranslate); start += chunkSize {
			end := start + chunkSize
			if end > len(toTranslate) {
				end = len(toTranslate)
			}
			chunk := toTranslate[start:end]
			var sb strings.Builder
			for _, it := range chunk {
				sb.WriteString(fmt.Sprintf("%d: %s\n", it.no, it.src))
			}
			system := `คุณคือผู้แปลชื่อตอนนิยายจีนเป็นภาษาไทย แปลเฉพาะชื่อตอน ให้ภาษาไทยธรรมชาติ สั้นกระชับ เก็บชื่อคน/สถานที่ด้วยการถอดเสียงแบบย่อ เอาต์พุตเป็น JSON object {"ตอนเลข": "ชื่อไทย"} เท่านั้น ไม่มีข้อความอื่น อย่าใส่เลขตอนในชื่อไทย`
			user := "แปลชื่อตอนต่อไปนี้เป็นภาษาไทย:\n" + sb.String()

			out, _, err := client.CompleteWithFallback(context.Background(), system, user, []string{"kr/deepseek-3.2"}, 0.1)
			if err != nil {
				fmt.Println("LLM failed:", err)
				os.Exit(1)
			}
			out = strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(out), "```json"))
			out = strings.TrimSuffix(strings.TrimSpace(out), "```")
			var parsed map[string]any
			if err := json.Unmarshal([]byte(out), &parsed); err != nil {
				fmt.Println("parse failed, raw head:", out[:min(len(out), 300)])
				os.Exit(1)
			}
			for _, it := range chunk {
				thai, ok := parsed[fmt.Sprint(it.no)].(string)
				if !ok || strings.TrimSpace(thai) == "" {
					continue
				}
				title, _ := it.doc["title"].(map[string]any)
				title["source"] = it.src
				title["translated"] = strings.TrimSpace(thai)
				if writeDoc(it.thPath, it.doc) {
					written++
				}
			}
			fmt.Printf("chunk %d-%d: %d written\n", start+1, end, written)
		}
		fmt.Printf("translated+wrote: %d/%d\n", written, len(toTranslate))
	}
	for i, it := range items {
		if keep[i] {
			title, _ := it.doc["title"].(map[string]any)
			if src, _ := title["source"].(string); src == "" {
				title["source"] = it.src
				if writeDoc(it.thPath, it.doc) {
					fmt.Printf("backfilled source for %04d\n", it.no)
				}
			}
		}
	}
}

func writeDoc(path string, doc map[string]any) bool {
	data, err := json.Marshal(doc)
	if err != nil {
		return false
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		fmt.Println("write fail:", path, err)
		return false
	}
	return true
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
