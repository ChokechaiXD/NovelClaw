package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net"
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
	browserFlag := flag.Bool("browser", true, "Open NovelClaw in the default browser")
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
	if *routerFlag != "" || *modelFlag != "" || *keyFlag != "" {
		cfg.ApplyRuntimeProviderOverride(*routerFlag, *keyFlag, *modelFlag)
	}

	localURL := browserURL(cfg.Host, cfg.Port)
	addr := fmt.Sprintf("%s:%d", cfg.Host, cfg.Port)
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		if novelClawResponding(localURL) {
			fmt.Printf("NovelClaw is already running at %s\n", localURL)
			if *browserFlag {
				if openErr := openBrowser(localURL); openErr != nil {
					log.Printf("Could not open browser: %v", openErr)
				}
			}
			return
		}
		log.Fatalf("Cannot start NovelClaw on %s: %v", addr, err)
	}
	defer listener.Close()

	store := storage.NewStore(cfg.DataDir)
	router, apiHandler := api.SetupRouter(cfg, store)
	go api.MaybeAutoBackup(cfg)
	go apiHandler.ResumeInterruptedJobs()

	server := &http.Server{
		Addr:              addr,
		Handler:           router,
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    1 << 20,
	}

	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)
	serveErr := make(chan error, 1)

	go func() {
		api.PrintBanner(cfg.Port)
		if err := server.Serve(listener); err != nil && err != http.ErrServerClosed {
			serveErr <- err
		}
	}()

	if *browserFlag {
		go openBrowserWhenReady(localURL)
	}

	select {
	case <-stopChan:
	case err := <-serveErr:
		log.Fatalf("Server error: %v", err)
	}

	fmt.Println("\nShutting down NovelClaw cleanly...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("Shutdown error: %v", err)
	}
	fmt.Println("Goodbye!")
}
