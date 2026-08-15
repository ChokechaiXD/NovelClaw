package scraper

import (
	"fmt"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

// GenericScraper fallback for any web novel page
type GenericScraper struct{}

func NewGenericScraper() *GenericScraper {
	return &GenericScraper{}
}

func (s *GenericScraper) CanHandle(rawURL string) bool {
	return true // Fallback handles all URLs
}

func (s *GenericScraper) FetchChapter(chapterURL string) (*ScrapedChapter, error) {
	doc, err := fetchHTMLDoc(chapterURL)
	if err != nil {
		return nil, fmt.Errorf("generic fetch failed: %w", err)
	}

	// 1. Extract Title
	title := strings.TrimSpace(doc.Find("h1, .chapter-title, .title, .entry-title").First().Text())
	if title == "" {
		title = strings.TrimSpace(doc.Find("title").Text())
	}

	chNo := extractChapterNumber(title)
	if chNo == 0 {
		chNo = extractChapterNumber(chapterURL)
	}

	// 2. Select best container
	selectors := []string{
		"#content", ".content", ".chapter-content", ".entry-content",
		".reading-content", ".article-content", ".post-content", "article",
		"#chapter-content", ".text-content",
	}

	var bestSel *goquery.Selection
	for _, sel := range selectors {
		node := doc.Find(sel).First()
		if node.Length() > 0 && len(node.Text()) > 200 {
			bestSel = node
			break
		}
	}

	if bestSel == nil {
		bestSel = doc.Find("body")
	}

	// Clean garbage tags
	bestSel.Find("script, style, nav, header, footer, iframe, .ad, .ads, .comment, .share").Remove()

	htmlText, _ := bestSel.Html()
	htmlText = strings.ReplaceAll(htmlText, "<br/>", "\n")
	htmlText = strings.ReplaceAll(htmlText, "<br>", "\n")
	htmlText = strings.ReplaceAll(htmlText, "</p>", "\n")
	htmlText = strings.ReplaceAll(htmlText, "</div>", "\n")

	cleanDoc, _ := goquery.NewDocumentFromReader(strings.NewReader(htmlText))
	rawText := cleanDoc.Text()

	var paragraphs []string
	for _, line := range strings.Split(rawText, "\n") {
		trimmed := strings.TrimSpace(line)
		if len(trimmed) > 1 && !is69ShuJunk(trimmed) {
			paragraphs = append(paragraphs, trimmed)
		}
	}

	if len(paragraphs) == 0 {
		return nil, fmt.Errorf("no readable paragraphs found in %s", chapterURL)
	}

	return &ScrapedChapter{
		ChapterNo:  chNo,
		Title:      title,
		Paragraphs: paragraphs,
		URL:        chapterURL,
	}, nil
}

func (s *GenericScraper) FetchTOC(tocURL string) (*ScrapedNovelInfo, error) {
	doc, err := fetchHTMLDoc(tocURL)
	if err != nil {
		return nil, fmt.Errorf("generic TOC fetch failed: %w", err)
	}

	info := &ScrapedNovelInfo{}
	info.Title = strings.TrimSpace(doc.Find("h1, .novel-title, .book-title").First().Text())
	if info.Title == "" {
		info.Title = strings.TrimSpace(doc.Find("title").Text())
	}

	info.Description = strings.TrimSpace(doc.Find(".description, .intro, .summary, .synopsis").First().Text())
	info.CoverURL, _ = doc.Find(".cover img, .book-cover img, .poster img").First().Attr("src")

	return info, nil
}
