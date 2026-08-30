package scraper

import (
	"context"
	"encoding/json"
	"fmt"
	"net/url"
	"regexp"
	"strconv"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

// QidianScraper reads public pages from Qidian's mobile site.
// It deliberately refuses locked VIP chapters; NovelClaw never bypasses paywalls.
type QidianScraper struct{}

func NewQidianScraper() *QidianScraper { return &QidianScraper{} }

var (
	qidianBookPathRE    = regexp.MustCompile(`/book/(\d+)`)
	qidianChapterPathRE = regexp.MustCompile(`/chapter/(\d+)/(\d+)`)
)

func (s *QidianScraper) CanHandle(rawURL string) bool {
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil {
		return false
	}
	host := strings.ToLower(u.Hostname())
	return host == "qidian.com" || strings.HasSuffix(host, ".qidian.com")
}
func (s *QidianScraper) FetchChapter(rawURL string) (*ScrapedChapter, error) {
	return s.FetchChapterContext(context.Background(), rawURL)
}

func (s *QidianScraper) FetchTOC(rawURL string) (*ScrapedNovelInfo, error) {
	return s.FetchTOCContext(context.Background(), rawURL)
}

type qidianEnvelope struct {
	PageContext struct {
		PageProps struct {
			PageData json.RawMessage `json:"pageData"`
		} `json:"pageProps"`
	} `json:"pageContext"`
}

func decodeQidianPageData(doc *goquery.Document, out any) error {
	raw := strings.TrimSpace(doc.Find("script#vite-plugin-ssr_pageContext").First().Text())
	if raw == "" {
		return fmt.Errorf("Qidian page context not found")
	}
	var env qidianEnvelope
	if err := json.Unmarshal([]byte(raw), &env); err != nil {
		return fmt.Errorf("decode Qidian page context: %w", err)
	}
	if len(env.PageContext.PageProps.PageData) == 0 {
		return fmt.Errorf("Qidian page data is empty")
	}
	if err := json.Unmarshal(env.PageContext.PageProps.PageData, out); err != nil {
		return fmt.Errorf("decode Qidian page data: %w", err)
	}
	return nil
}

type qidianChapterData struct {
	ChapterInfo struct {
		ChapterID    int64  `json:"chapterId"`
		ChapterName  string `json:"chapterName"`
		ChapterOrder int    `json:"chapterOrder"`
		UUID         int    `json:"uuid"`
		Content      string `json:"content"`
		VIPStatus    int    `json:"vipStatus"`
		IsBuy        int    `json:"isBuy"`
	} `json:"chapterInfo"`
}

func (s *QidianScraper) FetchChapterContext(ctx context.Context, rawURL string) (*ScrapedChapter, error) {
	bookID, chapterID, err := qidianChapterIDs(rawURL)
	if err != nil {
		return nil, err
	}
	chapterURL := fmt.Sprintf("https://m.qidian.com/chapter/%s/%s/", bookID, chapterID)
	doc, err := fetchHTMLDocContext(ctx, chapterURL)
	if err != nil {
		return nil, fmt.Errorf("Qidian chapter fetch failed: %w", err)
	}
	var data qidianChapterData
	if err := decodeQidianPageData(doc, &data); err != nil {
		return nil, err
	}
	ci := data.ChapterInfo
	if ci.VIPStatus != 0 && ci.IsBuy == 0 {
		return nil, fmt.Errorf("Qidian chapter is VIP/locked; NovelClaw will not bypass the paywall")
	}
	paragraphs := qidianParagraphs(ci.Content)
	if len(paragraphs) == 0 {
		return nil, fmt.Errorf("Qidian chapter contains no public readable text")
	}
	chapterNo := extractChapterNumber(ci.ChapterName)
	if chapterNo == 0 {
		chapterNo = ci.ChapterOrder
	}
	if chapterNo == 0 {
		chapterNo = ci.UUID
	}
	return &ScrapedChapter{
		ChapterNo:  chapterNo,
		Title:      strings.TrimSpace(ci.ChapterName),
		Paragraphs: paragraphs,
		URL:        chapterURL,
	}, nil
}

func qidianParagraphs(fragment string) []string {
	fragment = strings.TrimSpace(fragment)
	if fragment == "" {
		return nil
	}
	doc, err := goquery.NewDocumentFromReader(strings.NewReader("<div id='qidian-content'>" + fragment + "</div>"))
	if err != nil {
		return nil
	}
	var paragraphs []string
	doc.Find("#qidian-content p").Each(func(_ int, p *goquery.Selection) {
		text := strings.TrimSpace(p.Text())
		if text != "" {
			paragraphs = append(paragraphs, text)
		}
	})
	if len(paragraphs) > 0 {
		return paragraphs
	}
	text := strings.TrimSpace(doc.Find("#qidian-content").Text())
	if text != "" {
		return []string{text}
	}
	return nil
}

type qidianCatalogData struct {
	BookName        string `json:"bookName"`
	BookID          int64  `json:"bookId"`
	ChapterTotalCnt int    `json:"chapterTotalCnt"`
	AuthorInfo      struct {
		AuthorName string `json:"authorName"`
	} `json:"authorInfo"`
	Volumes []struct {
		VIPStatus int `json:"vS"`
		Chapters  []struct {
			Status int    `json:"sS"`
			Name   string `json:"cN"`
			ID     int64  `json:"id"`
			UUID   int    `json:"uuid"`
		} `json:"cs"`
	} `json:"vs"`
}

type qidianBookData struct {
	BookInfo struct {
		BookID      int64  `json:"bookId"`
		BookName    string `json:"bookName"`
		AuthorName  string `json:"authorName"`
		Description string `json:"desc"`
	} `json:"bookInfo"`
}

func (s *QidianScraper) FetchTOCContext(ctx context.Context, rawURL string) (*ScrapedNovelInfo, error) {
	bookID, err := qidianBookID(rawURL)
	if err != nil {
		return nil, err
	}
	bookURL := fmt.Sprintf("https://m.qidian.com/book/%s/", bookID)
	catalogURL := fmt.Sprintf("https://m.qidian.com/book/%s/catalog/", bookID)

	bookDoc, err := fetchHTMLDocContext(ctx, bookURL)
	if err != nil {
		return nil, fmt.Errorf("Qidian book fetch failed: %w", err)
	}
	var book qidianBookData
	if err := decodeQidianPageData(bookDoc, &book); err != nil {
		return nil, err
	}

	catalogDoc, err := fetchHTMLDocContext(ctx, catalogURL)
	if err != nil {
		return nil, fmt.Errorf("Qidian catalog fetch failed: %w", err)
	}
	var catalog qidianCatalogData
	if err := decodeQidianPageData(catalogDoc, &catalog); err != nil {
		return nil, err
	}

	info := &ScrapedNovelInfo{
		Title:       strings.TrimSpace(book.BookInfo.BookName),
		Author:      strings.TrimSpace(book.BookInfo.AuthorName),
		Description: strings.TrimSpace(book.BookInfo.Description),
	}
	if info.Title == "" {
		info.Title = strings.TrimSpace(catalog.BookName)
	}
	if info.Author == "" {
		info.Author = strings.TrimSpace(catalog.AuthorInfo.AuthorName)
	}
	cover, _ := bookDoc.Find("meta[property='og:image']").First().Attr("content")
	if strings.HasPrefix(cover, "//") {
		cover = "https:" + cover
	}
	info.CoverURL = strings.TrimSpace(cover)

	// Keep the complete official catalog. Locked chapters are metadata-only;
	// FetchChapterContext still refuses their text unless Qidian reports access.
	for _, volume := range catalog.Volumes {
		for _, ch := range volume.Chapters {
			if ch.ID <= 0 {
				continue
			}
			// Use official catalog order as the stable internal chapter number.
			// Some Qidian titles intentionally repeat/skip displayed numbers.
			chapterNo := len(info.Chapters) + 1
			info.Chapters = append(info.Chapters, ScrapedChapter{
				ChapterNo: chapterNo,
				Title:     strings.TrimSpace(ch.Name),
				URL:       fmt.Sprintf("https://m.qidian.com/chapter/%s/%d/", bookID, ch.ID),
				Locked:    volume.VIPStatus != 0,
			})
		}
	}
	if len(info.Chapters) == 0 {
		return nil, fmt.Errorf("Qidian catalog has no chapters")
	}
	return info, nil
}
func qidianBookID(rawURL string) (string, error) {
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil {
		return "", fmt.Errorf("invalid Qidian URL: %w", err)
	}
	if m := qidianBookPathRE.FindStringSubmatch(u.Path); len(m) == 2 {
		return m[1], nil
	}
	if m := qidianChapterPathRE.FindStringSubmatch(u.Path); len(m) == 3 {
		return m[1], nil
	}
	return "", fmt.Errorf("Qidian book ID not found in URL")
}

func qidianChapterIDs(rawURL string) (string, string, error) {
	u, err := url.Parse(strings.TrimSpace(rawURL))
	if err != nil {
		return "", "", fmt.Errorf("invalid Qidian URL: %w", err)
	}
	m := qidianChapterPathRE.FindStringSubmatch(u.Path)
	if len(m) != 3 {
		return "", "", fmt.Errorf("Qidian chapter URL must include book and chapter IDs")
	}
	if _, err := strconv.ParseInt(m[1], 10, 64); err != nil {
		return "", "", fmt.Errorf("invalid Qidian book ID")
	}
	if _, err := strconv.ParseInt(m[2], 10, 64); err != nil {
		return "", "", fmt.Errorf("invalid Qidian chapter ID")
	}
	return m[1], m[2], nil
}
