# DEV_REPORT — NovelClaw (Go single-binary)

**วันท่ี:** 2026-08-18
**ผู้ตรวจพัฒนา:** SORA (ผ่าน A2A จาก MIKA)
**Commit:** `ba07093` บน branch `main`

---

## 1. สถานะกอนแก้

- `go build ./...` — ผ่าน
- `go vet ./...` — สะอาด
- `go test ./...` — ผ่านทุก package (api, config, scraper, storage, translator)
- Repo มี uncommitted changes ค้างอยูกอนแล่ว (app.js typo fix, style.css variables, run.bat port check, qa_scan.py) — **ไมไดแตะ** เพราะไมใชงานรอบน้ี

## 2. ส่ิงท่ีพบ (อานครบทุกไฟล)

โครงสร้่างโดยรวมดี: path traversal ถูกป้่องกัันดว้ย `pathSafeSlug`/`safeSlug`, SSRF guard ครบท้ัง direct + redirect, config ใช้ mutex ป้่องกััน, chapter files เขียนแบบ atomic, API key mask กอนสงออก API

จุดอ่อนท่ีพบและแก้ 3 จุด (รายละเอียดหวัข้่อ 3) และจุดท่ีรบัรู็แต่ยัังไมแก้ (หวัข้่อ 5)

## 3. ส่ิงท่ีแก้ (3 จุด, diff รวม +21/-6 เสน)

### 3.1 fix: data race ท่ี `cfg.Provider`

**ปญหา:** `UpdateConfig` (handler.go) เขียน `c.Provider` ภายใต้ `cfg.mu` แต `GetConfig` อ่าน `h.cfg.Provider` ตรงๆ โดยไมล๊อก ฟิลดอื่่นๆ (RouterURL, APIKey, DefaultModel, Temperature) มี thread-safe getter หมดแล่ว ยกเว้นฟิลดน้ี — เป็็น data race ตาม Go memory model ถ้่ามี request เข้่า `/api/config` พร้่อมกัันกัับการอัปเดต config

**การแก้:**
- `internal/config/config.go`: เพิ่่ม `GetProvider()` (ล๊อกกอนอ่าน เหมืือน getter ตััวอื่่น)
- `internal/api/handler.go`: `GetConfig` ใช้ `h.cfg.GetProvider()` แทนอานตรง
- `internal/config/config_test.go`: เพิ่่ม `TestProviderGetter`

### 3.2 fix: atomic writes สำหรัับ novel.json / glossary.json / bookmark.json

**ปญหา:** `SaveChapter` ใช้ `writeFileAtomic` (temp + rename) แล่ว แต `SaveNovel`, `SaveGlossary`, `SaveBookmark` ยัังใช้ `os.WriteFile` ตรงๆ ถ้่า process ตาย/ไฟฟ้่าดบั กลางคััน เขียน ไฟล metadata เหล่าน้ีอาจพังก่ึงกลาง (half-written JSON) แล้้วอานไมได้อีก

**การแก้:** `internal/storage/storage.go` — เปล่่ียน 3 จุดน้ีให้ใช้ `writeFileAtomic` ท่ีมีอย่่แล้้ว (ไมเพิ่่ม dependency, ไมเปล่่ียนพฤตติกรรมปกตติ)

### 3.3 fix: จำกััดขนาด response body ใน `FetchModels`

**ปญหา:** `translator.Client.FetchModels` อ่าน body ดว้ย `io.ReadAll` ไมมขีีดจำกััด `routerUrl` เป็็นคาท่ี user ตั้่งเองผาน UI (trust boundary) และ endpoint `/api/models` เปิิดบน LAN — gateway ท่ีตอบ body ขนาดใหญไมจบจะกิน memory จน process ล้ม

**การแก้:** `internal/translator/client.go` — ใช้ `io.LimitReader` (10 MB สำหรัับ body ปกตติ, 4 KB สำหรัับ error body)

## 4. ผลการทดสอบ

```
go build ./...   → BUILD OK
go vet ./...     → clean
go test ./...    → ok  novelclaw/internal/api
                   ok  novelclaw/internal/config   (รวม TestProviderGetter ใหม)
                   ok  novelclaw/internal/scraper
                   ok  novelclaw/internal/storage
                   ok  novelclaw/internal/translator
```

หมายเหตุ: `go test -race` รันบนเครื่่องน้ีไมได้ (ต้อ้ง CGO/gcc ซ่ึงไมไดตติดตั้่ง) — การแก้ race ใน 3.1 พิสูจนจ์าก code path โดยตรง (เขียนใตล๊อก/อานไมล๊อก)

## 5. แนะนำทำตอ (ไมไดแก้รอบน้ี)

1. **ติดตั้่ง gcc แล้้วรัน `go test -race ./...`** — ยืนยัันวาไมม race อื่่นซอ้น (โดยเฉพาะ SSE broker + job maps)
2. **`GetChapter` มี write side-effect ใน GET handler** (Zero-Hanzi Interceptor บัันทึกไฟลตอนอาน) — ทำให้อานหน้่าเดิิมซ้้ำๆ กัันได้อีก และเป็็น write ท่ีไมม idempotency พิจารณาแยกออกรันเป็็น background job หรืือทำตอนแปลเสร็็จเท่านั้่น
3. **`updateNovelStats` รันเป็็น goroutine ทุกครั้่งท่ี SaveChapter** — ถ้่า import 100 ตอน จะม 100 goroutine แย่งกัันอัปเดต novel.json (ม mutex ป้่องกััน race แตเสีีย I/O เปล่า) อาจ debounce หรืืออัปเดตตอนท้่าย job
4. **Import TOC loop ไมม cancel** — `POST /api/import` เริ่่ม background goroutine ท่ียกเลิิกไมได (ต่างจาก translate job ท่ีมี CancelJob) ถ้่า TOC มเป็็นพันตอน + sleep 400ms/ตอน จะค้่างเป็็นชั่่วโมง
5. **`Complete` retry 3 ครั้่งท้ัง 4xx ท่ีไมใช 429** — เชน 401/403 (key พลาด) จะ retry ใหเ้สีียเวลา กอนจะ fail; ควร fail ทัันทีสำหรัับ 4xx ท่ีไมใช 429
6. **uncommitted changes ท่ีค้างอย่่** (app.js, style.css, run.bat, qa_scan.py + ไฟล QA ท่ีเพิ่่งมาใหม) — ควรตรวจแล้้ว commit แยก หรืือท้ิง ถ้่าไมต้อ้งการ

## 6. ข้อจำกััดของงานรอบน้ี

- ไมไดแตะ `novels/` และ `config.json` ตามเงื่่อนไข
- ไมไดเปล่่ียนพฤตติกรรมท่ีใช้งานได้อันใด — ท้ัง 3 จุดเป็็นการป้่องกัันความเสีียหาย/ความปลอดภััย ล้้วนๆ
