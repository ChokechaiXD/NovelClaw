package api

import (
	"archive/zip"
	"bytes"
	"errors"
	"testing"
)

func TestBuildEPUBProducesReadableArchive(t *testing.T) {
	chapters := []exportChapter{{
		ChapterNo: 1,
		Title:     "ตอนที่ 1",
		Paragraphs: []string{
			"ข้อความทดสอบ <ปลอดภัย>",
		},
	}}
	var buf bytes.Buffer
	if err := buildEPUB(&buf, "book", "นิยายทดสอบ", "ผู้แต่ง", chapters); err != nil {
		t.Fatal(err)
	}

	zr, err := zip.NewReader(bytes.NewReader(buf.Bytes()), int64(buf.Len()))
	if err != nil {
		t.Fatalf("open generated EPUB: %v", err)
	}
	want := map[string]bool{
		"mimetype":               false,
		"META-INF/container.xml": false,
		"OEBPS/style.css":        false,
		"OEBPS/chapter_1.xhtml":  false,
		"OEBPS/content.opf":      false,
		"OEBPS/toc.ncx":          false,
	}
	for _, file := range zr.File {
		if _, ok := want[file.Name]; ok {
			want[file.Name] = true
		}
	}
	for name, found := range want {
		if !found {
			t.Errorf("missing EPUB entry %s", name)
		}
	}
}

type failWriter struct{}

func (failWriter) Write([]byte) (int, error) {
	return 0, errors.New("disk write failed")
}
func TestBuildEPUBPropagatesWriterFailure(t *testing.T) {
	err := buildEPUB(failWriter{}, "book", "title", "author", []exportChapter{{
		ChapterNo:  1,
		Title:      "one",
		Paragraphs: []string{"body"},
	}})
	if err == nil {
		t.Fatal("expected writer failure")
	}
}
