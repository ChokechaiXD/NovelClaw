package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"novelclaw/internal/api"
	"novelclaw/internal/config"
	"novelclaw/internal/storage"
)

func main() {
	portFlag := flag.Int("port", 0, "Web server port (default: 4890 or PORT env)")
	hostFlag := flag.String("host", "", "Web server host bind (default: 0.0.0.0)")
	dataDirFlag := flag.String("data", "", "Data directory path (default: ./novels)")
	routerFlag := flag.String("router", "", "9Router or OpenAI Base URL")
	modelFlag := flag.String("model", "", "Default translation model")
	keyFlag := flag.String("key", "", "API Key for translation endpoint")
	configPathFlag := flag.String("config", "config.json", "Config file path")
	flag.Parse()

	cfg := config.LoadConfig(*configPathFlag)

	if *portFlag > 0 {
		cfg.Port = *portFlag
	}
	if *hostFlag != "" {
		cfg.Host = *hostFlag
	}
	if *dataDirFlag != "" {
		cfg.DataDir = *dataDirFlag
	}
	// Provider CLI flags are runtime-only overrides. Route them through the
	// same provider registry used by the web UI instead of mutating legacy
	// compatibility fields directly.
	if *routerFlag != "" || *modelFlag != "" || *keyFlag != "" {
		cfg.ApplyRuntimeProviderOverride(*routerFlag, *keyFlag, *modelFlag)
	}

	store := storage.NewStore(cfg.DataDir)
	router, apiHandler := api.SetupRouter(cfg, store)

	// Safety net: snapshot the data dir at startup when the newest archive
	// is older than 24h (novels/ is no longer in git — this is the backup).
	go api.MaybeAutoBackup(cfg)

	// Restart-safe queues: pick up translation jobs that died mid-run.
	go apiHandler.ResumeInterruptedJobs()

	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	server := &http.Server{
		Addr:              addr,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    1 << 20,
		// No WriteTimeout: /events is a long-lived SSE connection.
	}

	// Graceful shutdown listener
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		api.PrintBanner(cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	<-stopChan
	fmt.Println("\nShutting down NovelClaw cleanly...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("Shutdown error: %v", err)
	}
	fmt.Println("Goodbye!")
}
