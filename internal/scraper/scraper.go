package scraper

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
	"golang.org/x/text/encoding/simplifiedchinese"
	"golang.org/x/text/transform"
)

// ScrapedChapter represents the extracted chapter details
type ScrapedChapter struct {
	ChapterNo  int      `json:"chapterNo"`
	Title      string   `json:"title"`
	Paragraphs []string `json:"paragraphs"`
	URL        string   `json:"url"`
}

// ScrapedNovelInfo represents metadata and chapter links from TOC
type ScrapedNovelInfo struct {
	Title       string           `json:"title"`
	Author      string           `json:"author"`
	Description string           `json:"description"`
	CoverURL    string           `json:"coverUrl"`
	Chapters    []ScrapedChapter `json:"chapters"`
}

// Scraper defines the interface for novel site extractors
type Scraper interface {
	CanHandle(url string) bool
	FetchChapter(url string) (*ScrapedChapter, error)
	FetchTOC(url string) (*ScrapedNovelInfo, error)
}

var client = &http.Client{
	Timeout: 20 * time.Second,
	// Re-validate every redirect hop so a public URL cannot bounce us into
	// a private address (SSRF).
	CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if len(via) >= 5 {
			return fmt.Errorf("too many redirects")
		}
		return validatePublicURL(req.URL.String())
	},
}

// UniversalScraper dispatches to specific site scraper or fallback generic
type UniversalScraper struct {
	scrapers []Scraper
}

// NewUniversalScraper initializes all scrapers
func NewUniversalScraper() *UniversalScraper {
	return &UniversalScraper{
		scrapers: []Scraper{
			NewShu69Scraper(),
			NewGenericScraper(),
		},
	}
}

// FetchChapter extracts chapter text from any URL
func (u *UniversalScraper) FetchChapter(url string) (*ScrapedChapter, error) {
	for _, s := range u.scrapers {
		if s.CanHandle(url) {
			return s.FetchChapter(url)
		}
	}
	return nil, fmt.Errorf("no scraper found for url: %s", url)
}

// FetchTOC extracts novel metadata and chapter list from a novel homepage
func (u *UniversalScraper) FetchTOC(url string) (*ScrapedNovelInfo, error) {
	for _, s := range u.scrapers {
		if s.CanHandle(url) {
			return s.FetchTOC(url)
		}
	}
	return nil, fmt.Errorf("no scraper found for url: %s", url)
}

// Helper: fetch HTML with proper User-Agent and automatic encoding detection (GBK / UTF-8)
func fetchHTMLDoc(targetURL string) (*goquery.Document, error) {
	if err := validatePublicURL(targetURL); err != nil {
		return nil, err
	}

	req, err := http.NewRequest("GET", targetURL, nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
	req.Header.Set("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, resp.Status)
	}

	bodyBytes, err := io.ReadAll(io.LimitReader(resp.Body, 10<<20))
	if err != nil {
		return nil, err
	}

	// Detect if page uses GBK / GB2312 / GB18030 or contains non-UTF-8 bytes
	contentType := strings.ToLower(resp.Header.Get("Content-Type"))
	bodySample := strings.ToLower(string(bodyBytes[:min(2048, len(bodyBytes))]))
	isGBK := strings.Contains(contentType, "gbk") || strings.Contains(contentType, "gb2312") ||
		strings.Contains(contentType, "gb18030") || strings.Contains(bodySample, "gbk") ||
		strings.Contains(bodySample, "gb2312") || strings.Contains(bodySample, "gb18030")

	var reader io.Reader = bytes.NewReader(bodyBytes)
	if isGBK {
		reader = transform.NewReader(reader, simplifiedchinese.GB18030.NewDecoder())
	}

	return goquery.NewDocumentFromReader(reader)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
