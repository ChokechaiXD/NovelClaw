package api

import (
	"archive/zip"
	"fmt"
	"html"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// ExportNovel exports translated chapters in TXT, Markdown, or EPUB format
func (h *APIHandler) ExportNovel(w http.ResponseWriter, r *http.Request) {
	slug := safeSlug(r.PathValue("slug"))
	format := r.URL.Query().Get("format")
	if format == "" {
		format = "txt"
	}
	format = strings.ToLower(format)

	novel, err := h.store.GetNovel(slug)
	if err != nil {
		WriteError(w, http.StatusNotFound, "Novel not found")
		return
	}

	chapters, err := h.store.ListChapters(slug)
	if err != nil || len(chapters) == 0 {
		WriteError(w, http.StatusNotFound, "No chapters found to export")
		return
	}

	// Chapter numbers can have gaps (e.g. 1..72 then 86..88), so bound the
	// range by real chapter numbers, not by the slice length.
	maxChNo := chapters[len(chapters)-1].ChapterNo

	startNo := 1
	if s := r.URL.Query().Get("start"); s != "" {
		if v, err := strconv.Atoi(s); err == nil && v > 0 {
			startNo = v
		}
	}

	endNo := maxChNo
	if s := r.URL.Query().Get("end"); s != "" {
		if v, err := strconv.Atoi(s); err == nil && v > 0 && v <= maxChNo {
			endNo = v
		}
	}

	// Fetch full content of all translated chapters in range
	type ExportChapter struct {
		ChapterNo  int
		Title      string
		Paragraphs []string
	}
	var exportList []ExportChapter

	for _, meta := range chapters {
		chNo := meta.ChapterNo
		if chNo < startNo || chNo > endNo {
			continue
		}
		content, err := h.store.GetChapter(slug, chNo)
		if err != nil || len(content.TranslatedText) == 0 {
			continue
		}
		title := content.TranslatedTitle
		if title == "" {
			title = fmt.Sprintf("ตอนที่ %d", chNo)
		}
		exportList = append(exportList, ExportChapter{
			ChapterNo:  chNo,
			Title:      title,
			Paragraphs: content.TranslatedText,
		})
	}

	if len(exportList) == 0 {
		WriteError(w, http.StatusBadRequest, "No translated chapters found in the specified range")
		return
	}

	novelTitle := novel.TranslatedTitle
	if novelTitle == "" {
		novelTitle = novel.Title
	}
	if novelTitle == "" {
		novelTitle = slug
	}

	safeFileName := sanitizeSlug(novelTitle)
	if safeFileName == "" {
		safeFileName = "novel"
	}

	switch format {
	case "txt":
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s_ch%d-%d.txt"`, safeFileName, startNo, endNo))

		// UTF-8 BOM for Windows compatibility
		_, _ = w.Write([]byte{0xEF, 0xBB, 0xBF})

		var b strings.Builder
		b.WriteString(fmt.Sprintf("====================================================\n"))
		b.WriteString(fmt.Sprintf(" ชื่อเรื่อง: %s\n", novelTitle))
		if novel.Author != "" {
			b.WriteString(fmt.Sprintf(" ผู้แต่ง: %s\n", novel.Author))
		}
		b.WriteString(fmt.Sprintf(" ตอนที่: %d - %d (รวม %d ตอน)\n", startNo, endNo, len(exportList)))
		b.WriteString(fmt.Sprintf(" ส่งออกเมื่อ: %s\n", time.Now().Format("02/01/2006 15:04:05")))
		b.WriteString(fmt.Sprintf(" แปลและจัดทำโดย: NovelClaw AI\n"))
		b.WriteString(fmt.Sprintf("====================================================\n\n\n"))

		for _, ch := range exportList {
			b.WriteString(fmt.Sprintf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"))
			b.WriteString(fmt.Sprintf(" %s\n", ch.Title))
			b.WriteString(fmt.Sprintf("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"))
			for _, p := range ch.Paragraphs {
				b.WriteString("  " + p + "\n\n")
			}
			b.WriteString("\n\n")
		}
		_, _ = w.Write([]byte(b.String()))

	case "md", "markdown":
		w.Header().Set("Content-Type", "text/markdown; charset=utf-8")
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s_ch%d-%d.md"`, safeFileName, startNo, endNo))

		var b strings.Builder
		b.WriteString(fmt.Sprintf("# %s\n\n", novelTitle))
		if novel.Author != "" {
			b.WriteString(fmt.Sprintf("**ผู้แต่ง**: %s  \n", novel.Author))
		}
		b.WriteString(fmt.Sprintf("**จำนวนตอน**: %d - %d  \n", startNo, endNo))
		b.WriteString(fmt.Sprintf("**วันที่ส่งออก**: %s  \n\n---\n\n", time.Now().Format("02/01/2006 15:04")))

		for _, ch := range exportList {
			b.WriteString(fmt.Sprintf("## %s\n\n", ch.Title))
			for _, p := range ch.Paragraphs {
				b.WriteString(p + "\n\n")
			}
			b.WriteString("\n---\n\n")
		}
		_, _ = w.Write([]byte(b.String()))

	case "epub":
		w.Header().Set("Content-Type", "application/epub+zip")
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s_ch%d-%d.epub"`, safeFileName, startNo, endNo))

		zw := zip.NewWriter(w)
		defer zw.Close()

		// 1. mimetype (Uncompressed)
		header := &zip.FileHeader{
			Name:   "mimetype",
			Method: zip.Store,
		}
		mw, err := zw.CreateHeader(header)
		if err != nil {
			WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}
		_, _ = mw.Write([]byte("application/epub+zip"))

		// 2. META-INF/container.xml
		cw, _ := zw.Create("META-INF/container.xml")
		_, _ = cw.Write([]byte(`<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>`))

		// 3. OEBPS/style.css
		cssW, _ := zw.Create("OEBPS/style.css")
		_, _ = cssW.Write([]byte(`body { font-family: 'Sarabun', sans-serif; line-height: 1.8; margin: 5%; color: #333; }
h1, h2 { text-align: center; color: #111; margin-bottom: 2em; }
p { text-indent: 1.5em; margin: 0.8em 0; }`))

		// 4. Chapters
		for idx, ch := range exportList {
			chFileName := fmt.Sprintf("OEBPS/chapter_%d.xhtml", idx+1)
			chW, _ := zw.Create(chFileName)

			var parasHtml strings.Builder
			for _, p := range ch.Paragraphs {
				parasHtml.WriteString(fmt.Sprintf("    <p>%s</p>\n", html.EscapeString(p)))
			}

			chContent := fmt.Sprintf(`<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="th">
<head>
  <title>%s</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <h2>%s</h2>
%s
</body>
</html>`, html.EscapeString(ch.Title), html.EscapeString(ch.Title), parasHtml.String())
			_, _ = chW.Write([]byte(chContent))
		}

		// 5. OEBPS/content.opf
		opfW, _ := zw.Create("OEBPS/content.opf")
		var manifestItems strings.Builder
		var spineItems strings.Builder

		for idx := range exportList {
			id := fmt.Sprintf("ch_%d", idx+1)
			href := fmt.Sprintf("chapter_%d.xhtml", idx+1)
			manifestItems.WriteString(fmt.Sprintf(`    <item id="%s" href="%s" media-type="application/xhtml+xml"/>`+"\n", id, href))
			spineItems.WriteString(fmt.Sprintf(`    <itemref idref="%s"/>`+"\n", id))
		}

		opfContent := fmt.Sprintf(`<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">urn:uuid:novelclaw-%s</dc:identifier>
    <dc:title>%s</dc:title>
    <dc:language>th</dc:language>
    <dc:creator>%s</dc:creator>
    <dc:publisher>NovelClaw AI</dc:publisher>
    <meta property="dcterms:modified">%s</meta>
  </metadata>
  <manifest>
    <item id="style" href="style.css" media-type="text/css"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
%s  </manifest>
  <spine toc="ncx">
%s  </spine>
</package>`, slug, html.EscapeString(novelTitle), html.EscapeString(novel.Author), time.Now().UTC().Format("2006-01-02T15:04:05Z"), manifestItems.String(), spineItems.String())
		_, _ = opfW.Write([]byte(opfContent))

		// 6. OEBPS/toc.ncx
		ncxW, _ := zw.Create("OEBPS/toc.ncx")
		var navPoints strings.Builder
		for idx, ch := range exportList {
			navPoints.WriteString(fmt.Sprintf(`    <navPoint id="navPoint-%d" playOrder="%d">
      <navLabel><text>%s</text></navLabel>
      <content src="chapter_%d.xhtml"/>
    </navPoint>
`, idx+1, idx+1, html.EscapeString(ch.Title), idx+1))
		}

		ncxContent := fmt.Sprintf(`<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:novelclaw-%s"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>%s</text></docTitle>
  <navMap>
%s  </navMap>
</ncx>`, slug, html.EscapeString(novelTitle), navPoints.String())
		_, _ = ncxW.Write([]byte(ncxContent))

	default:
		WriteError(w, http.StatusBadRequest, "Unsupported export format. Use txt, markdown, or epub")
	}
}
