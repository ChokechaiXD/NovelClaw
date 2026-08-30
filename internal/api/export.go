package api

import (
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"

	"novelclaw/internal/storage"
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
		status := http.StatusInternalServerError
		if errors.Is(err, storage.ErrNovelNotFound) {
			status = http.StatusNotFound
		}
		WriteError(w, status, err.Error())
		return
	}

	chapters, err := h.store.ListChapters(slug)
	if err != nil {
		WriteError(w, http.StatusInternalServerError, err.Error())
		return
	}
	if len(chapters) == 0 {
		WriteError(w, http.StatusNotFound, "No chapters found to export")
		return
	}

	// Chapter numbers can have gaps (e.g. 1..72 then 86..88), so bound the
	// range by real chapter numbers, not by the slice length.
	maxChNo := chapters[len(chapters)-1].ChapterNo

	startNo, err := positiveQueryInt(r, "start", 1)
	if err != nil {
		WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	endNo, err := positiveQueryInt(r, "end", maxChNo)
	if err != nil {
		WriteError(w, http.StatusBadRequest, err.Error())
		return
	}
	if startNo > endNo {
		WriteError(w, http.StatusBadRequest, "end must be greater than or equal to start")
		return
	}
	if endNo > maxChNo {
		WriteError(w, http.StatusBadRequest, fmt.Sprintf("end exceeds highest chapter number %d", maxChNo))
		return
	}

	// Fetch full content of all translated chapters in range.
	var exportList []exportChapter

	for _, meta := range chapters {
		chNo := meta.ChapterNo
		if chNo < startNo || chNo > endNo {
			continue
		}
		content, err := h.store.GetChapter(slug, chNo)
		if err != nil {
			if errors.Is(err, storage.ErrChapterNotFound) {
				continue
			}
			WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}
		if len(content.TranslatedText) == 0 {
			continue
		}
		title := content.TranslatedTitle
		if title == "" {
			title = fmt.Sprintf("ตอนที่ %d", chNo)
		}
		exportList = append(exportList, exportChapter{
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
		payload := append([]byte{0xEF, 0xBB, 0xBF}, []byte(b.String())...)
		if _, err := w.Write(payload); err != nil {
			log.Printf("TXT export write failed for %s: %v", slug, err)
		}

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
		if _, err := w.Write([]byte(b.String())); err != nil {
			log.Printf("Markdown export write failed for %s: %v", slug, err)
		}

	case "epub":
		fileName := fmt.Sprintf("%s_ch%d-%d.epub", safeFileName, startNo, endNo)
		if err := serveEPUB(w, r, fileName, slug, novelTitle, novel.Author, exportList); err != nil {
			WriteError(w, http.StatusInternalServerError, fmt.Sprintf("EPUB export failed: %v", err))
		}
	default:
		WriteError(w, http.StatusBadRequest, "Unsupported export format. Use txt, markdown, or epub")
	}
}
