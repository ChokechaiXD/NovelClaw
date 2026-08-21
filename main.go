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
	portFlag := flag.Int("port", 0, "Web server port (default: 4173 or PORT env)")
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
	if *routerFlag != "" {
		cfg.RouterURL = *routerFlag
	}
	if *modelFlag != "" {
		cfg.DefaultModel = *modelFlag
	}
	if *keyFlag != "" {
		cfg.APIKey = *keyFlag
	}

	store := storage.NewStore(cfg.DataDir)
	router := api.SetupRouter(cfg, store)

	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	server := &http.Server{
		Addr:    addr,
		Handler: router,
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
