package scraper

import (
	"context"
	"fmt"
	"net/url"
	"regexp"
	"strconv"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

// Shu69Scraper specialized parser for 69shu / 69shuba domains
type Shu69Scraper struct{}

func NewShu69Scraper() *Shu69Scraper {
	return &Shu69Scraper{}
}

func (s *Shu69Scraper) CanHandle(rawURL string) bool {
	u, err := url.Parse(rawURL)
	if err != nil {
		return false
	}
	host := strings.ToLower(u.Host)
	return strings.Contains(host, "69shu") || strings.Contains(host, "69yuedu") || strings.Contains(host, "69xinshu")
}

func (s *Shu69Scraper) FetchChapter(chapterURL string) (*ScrapedChapter, error) {
	return s.FetchChapterContext(context.Background(), chapterURL)
}

func (s *Shu69Scraper) FetchChapterContext(ctx context.Context, chapterURL string) (*ScrapedChapter, error) {
	doc, err := fetchHTMLDocContext(ctx, chapterURL)
	if err != nil {
		return nil, fmt.Errorf("69shu fetch failed: %w", err)
	}

	// 1. Extract Title
	title := strings.TrimSpace(doc.Find("h1.hide720, h1, .txtnav h1").First().Text())
	title = clean69ShuTitle(title)

	// 2. Extract Chapter Number
	chNo := extractChapterNumber(title)
	if chNo == 0 {
		chNo = extractChapterNumber(chapterURL)
	}

	// 3. Extract Content paragraphs
	var paragraphs []string

	// Remove unwanted elements
	contentSel := doc.Find(".txtnav, #content, .content").First()
	contentSel.Find("script, style, h1, .hide720, .txtinfo, .bottom-ad, a").Remove()

	// Extract lines by replacing <br> with newline or iterating p/div
	htmlText, err := contentSel.Html()
	if err != nil {
		return nil, fmt.Errorf("read 69shu chapter HTML: %w", err)
	}
	htmlText = strings.ReplaceAll(htmlText, "<br/>", "\n")
	htmlText = strings.ReplaceAll(htmlText, "<br>", "\n")
	htmlText = strings.ReplaceAll(htmlText, "</p>", "\n")

	cleanDoc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlText))
	if err != nil {
		return nil, fmt.Errorf("parse 69shu chapter HTML: %w", err)
	}
	rawText := cleanDoc.Text()

	lines := strings.Split(rawText, "\n")
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if is69ShuJunk(trimmed) {
			continue
		}
		paragraphs = append(paragraphs, trimmed)
	}

	if len(paragraphs) == 0 {
		return nil, fmt.Errorf("no paragraphs extracted from %s", chapterURL)
	}

	return &ScrapedChapter{
		ChapterNo:  chNo,
		Title:      title,
		Paragraphs: paragraphs,
		URL:        chapterURL,
	}, nil
}

func (s *Shu69Scraper) FetchTOC(tocURL string) (*ScrapedNovelInfo, error) {
	return s.FetchTOCContext(context.Background(), tocURL)
}

func (s *Shu69Scraper) FetchTOCContext(ctx context.Context, tocURL string) (*ScrapedNovelInfo, error) {
	doc, err := fetchHTMLDocContext(ctx, tocURL)
	if err != nil {
		return nil, fmt.Errorf("69shu TOC fetch failed: %w", err)
	}

	info := &ScrapedNovelInfo{}

	// Extract book title & author
	info.Title = strings.TrimSpace(doc.Find(".booknav2 h1, .bookinfo h1, h1").First().Text())
	info.Author = strings.TrimSpace(doc.Find(".booknav2 p:contains('作者'), .bookinfo p:contains('作者')").First().Text())
	info.Author = strings.TrimPrefix(info.Author, "作者：")
	info.Author = strings.TrimPrefix(info.Author, "作者:")
	info.Author = strings.TrimSpace(info.Author)

	info.Description = strings.TrimSpace(doc.Find(".navtxt, .intro, .booknav2 .navtxt").First().Text())
	info.CoverURL, _ = doc.Find(".bookimg2 img, .bookcover img").First().Attr("src")

	// Parse chapter list
	baseURL, err := url.Parse(tocURL)
	if err != nil {
		return nil, fmt.Errorf("parse 69shu TOC URL: %w", err)
	}
	doc.Find("#catalog ul li a, .catalog ul li a, .mulu ul li a").Each(func(i int, sel *goquery.Selection) {
		chTitle := strings.TrimSpace(sel.Text())
		href, exists := sel.Attr("href")
		if !exists || href == "" || strings.HasPrefix(href, "javascript:") {
			return
		}

		chURL, err := baseURL.Parse(href)
		if err != nil {
			return
		}

		chNum := extractChapterNumber(chTitle)
		if chNum == 0 {
			chNum = i + 1
		}

		info.Chapters = append(info.Chapters, ScrapedChapter{
			ChapterNo: chNum,
			Title:     chTitle,
			URL:       chURL.String(),
		})
	})

	return info, nil
}

func clean69ShuTitle(raw string) string {
	raw = strings.ReplaceAll(raw, "黃金屋中文", "")
	raw = strings.ReplaceAll(raw, "黄金屋中文", "")
	raw = strings.ReplaceAll(raw, ">>", "")
	raw = strings.TrimSpace(raw)
	return raw
}

func is69ShuJunk(line string) bool {
	trimmed := strings.TrimSpace(line)
	if trimmed == "" {
		return true
	}
	lower := strings.ToLower(trimmed)
	junkKeywords := []string{
		"69shu", "69yuedu", "69xinshu", "黄金屋", "黃金屋",
		"请记住本书首发域名", "請記住本書首發域名",
		"本章完", "最新网址", "最新網址",
		"天才一秒记住", "筆趣閣", "笔趣阁",
		"章节错误,点此报送", "章节缺失",
	}
	for _, kw := range junkKeywords {
		if strings.Contains(lower, kw) {
			return true
		}
	}
	return false
}

var chNumRegex = regexp.MustCompile(`(?:第|Chapter\s*|ตอนที่\s*)(\d+)(?:章|回|節|节|:|\b)?`)

func extractChapterNumber(s string) int {
	matches := chNumRegex.FindStringSubmatch(s)
	if len(matches) > 1 {
		if num, err := strconv.Atoi(matches[1]); err == nil {
			return num
		}
	}
	return 0
}
