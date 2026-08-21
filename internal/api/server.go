package api

import (
	"fmt"
	"io/fs"
	"log"
	"net"
	"net/http"
	"strings"

	"novelclaw/internal/config"
	"novelclaw/internal/storage"
	"novelclaw/internal/web"
)

// SetupRouter creates the HTTP handler with all API endpoints and embedded static files.
// It also returns the APIHandler so main can resume persisted jobs with the
// same SSE broker the routes use.
func SetupRouter(cfg *config.AppConfig, store *storage.Store) (http.Handler, *APIHandler) {
	sse := NewSSEBroker()
	h := NewAPIHandler(cfg, store, sse)

	mux := http.NewServeMux()

	// SSE Events
	mux.Handle("GET /events", sse)

	// Novel Endpoints
	mux.HandleFunc("GET /api/novels", h.ListNovels)
	mux.HandleFunc("POST /api/novels", h.SaveNovel)
	mux.HandleFunc("GET /api/novels/{slug}", h.GetNovel)
	mux.HandleFunc("GET /api/novels/{slug}/chapters", h.ListChapters)
	mux.HandleFunc("GET /api/novels/{slug}/chapters/{num}", h.GetChapter)
	mux.HandleFunc("POST /api/novels/{slug}/chapters/{num}/repair", h.RepairChapter)
	mux.HandleFunc("GET /api/novels/{slug}/glossary", h.GetGlossary)
	mux.HandleFunc("POST /api/novels/{slug}/glossary", h.SaveGlossary)
	mux.HandleFunc("GET /api/novels/{slug}/glossary/check", h.GlossaryCheck)
	mux.HandleFunc("GET /api/novels/{slug}/bookmark", h.GetBookmark)
	mux.HandleFunc("POST /api/novels/{slug}/bookmark", h.SaveBookmark)
	mux.HandleFunc("GET /api/novels/{slug}/export", h.ExportNovel)

	// Backup
	mux.HandleFunc("POST /api/backup", h.BackupNow)
	mux.HandleFunc("GET /api/backup", h.ListBackupsHandler)

	// Actions
	mux.HandleFunc("POST /api/import", h.Import)
	mux.HandleFunc("POST /api/translate", h.Translate)
	mux.HandleFunc("POST /api/jobs/{id}/cancel", h.CancelJob)
	mux.HandleFunc("POST /api/novels/{slug}/glossary/discover", h.DiscoverGlossary)
	mux.HandleFunc("POST /api/audio/speech", h.GenerateSpeech)

	// System Config & Models
	mux.HandleFunc("GET /api/models", h.ListModels)
	mux.HandleFunc("GET /api/config", h.GetConfig)
	mux.HandleFunc("GET /api/detect-providers", h.DetectProviders)
	mux.HandleFunc("POST /api/config", h.UpdateConfig)

	// Embedded Static Assets
	staticFS, err := fs.Sub(web.StaticFiles, "static")
	if err != nil {
		log.Fatalf("Failed to load embedded static filesystem: %v", err)
	}

	fileServer := http.FileServer(http.FS(staticFS))
	mux.Handle("GET /", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// If path doesn't have an extension or is root, serve index.html for SPA routing
		path := r.URL.Path
		if path == "/" || !strings.Contains(path, ".") {
			r.URL.Path = "/"
		}
		fileServer.ServeHTTP(w, r)
	}))

	// Wrap with basic CORS / logging middleware
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}
		mux.ServeHTTP(w, r)
	})
	return handler, h
}

// GetLocalIPs returns active non-loopback IPv4 addresses
func GetLocalIPs() []string {
	var ips []string
	addrs, err := net.InterfaceAddrs()
	if err != nil {
		return ips
	}
	for _, addr := range addrs {
		if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
			if ipnet.IP.To4() != nil {
				ips = append(ips, ipnet.IP.String())
			}
		}
	}
	return ips
}

// PrintBanner prints server connection links
func PrintBanner(port int) {
	fmt.Println("==================================================")
	fmt.Println("       🐾 NOVELCLAW — High-Performance Reader      ")
	fmt.Println("==================================================")
	fmt.Printf(" [Local]: http://localhost:%d\n", port)
	for _, ip := range GetLocalIPs() {
		fmt.Printf(" [LAN]:   http://%s:%d\n", ip, port)
	}
	fmt.Println("==================================================")
}
