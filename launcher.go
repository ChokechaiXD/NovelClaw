package main

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"os/exec"
	"runtime"
	"strings"
	"time"
)

func browserURL(host string, port int) string {
	host = strings.TrimSpace(host)
	if host == "" || host == "0.0.0.0" || host == "::" {
		host = "127.0.0.1"
	}
	return "http://" + net.JoinHostPort(host, fmt.Sprintf("%d", port))
}

func openBrowser(url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	return cmd.Start()
}

func novelClawResponding(baseURL string) bool {
	client := &http.Client{Timeout: 900 * time.Millisecond}
	if resp, err := client.Get(baseURL + "/api/health"); err == nil {
		defer resp.Body.Close()
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		if resp.StatusCode == http.StatusOK && strings.Contains(string(body), `"app":"NovelClaw"`) {
			return true
		}
	}

	resp, err := client.Get(baseURL + "/")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 128<<10))
	if err != nil || resp.StatusCode != http.StatusOK {
		return false
	}
	text := string(body)
	return strings.Contains(text, "NovelClaw") && strings.Contains(text, "novel-grid")
}

func openBrowserWhenReady(baseURL string) {
	deadline := time.Now().Add(4 * time.Second)
	for time.Now().Before(deadline) {
		if novelClawResponding(baseURL) {
			_ = openBrowser(baseURL)
			return
		}
		time.Sleep(120 * time.Millisecond)
	}
}
