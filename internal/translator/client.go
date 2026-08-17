package translator

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"novelclaw/internal/config"
)

// LLMMessage represents a single chat message
type LLMMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ChatCompletionRequest is the OpenAI-compatible payload
type ChatCompletionRequest struct {
	Model       string       `json:"model"`
	Messages    []LLMMessage `json:"messages"`
	Temperature float64      `json:"temperature"`
	MaxTokens   int          `json:"max_tokens,omitempty"`
	Stream      bool         `json:"stream"`
}

// ChatCompletionResponse is the OpenAI-compatible response
type ChatCompletionResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
		Delta struct {
			Content string `json:"content"`
		} `json:"delta"`
	} `json:"choices"`
	Error *struct {
		Message string `json:"message"`
		Type    string `json:"type"`
	} `json:"error,omitempty"`
}

// Client interacts with 9Router or OpenAI-compatible endpoint
type Client struct {
	cfg        *config.AppConfig
	httpClient *http.Client
}

// NewClient creates a new LLM translation client
func NewClient(cfg *config.AppConfig) *Client {
	return &Client{
		cfg: cfg,
		httpClient: &http.Client{
			Timeout: 180 * time.Second,
		},
	}
}

// FetchModels queries 9Router/OpenRouter for active available models
// CompleteWithFallback tries each model in order ("" = config default) and
// returns the first successful result plus the model that produced it.
// Any non-context error moves to the next candidate, so a dead model in the
// chain can no longer kill an entire queue.
func (c *Client) CompleteWithFallback(ctx context.Context, systemPrompt, userPrompt string, models []string, temperature float64) (string, string, error) {
	if len(models) == 0 {
		models = []string{""}
	}
	var lastErr error
	for _, m := range models {
		out, err := c.Complete(ctx, systemPrompt, userPrompt, m, temperature)
		if err == nil {
			return out, m, nil
		}
		lastErr = err
		if ctx.Err() != nil {
			return "", "", lastErr
		}
	}
	return "", "", lastErr
}

func (c *Client) FetchModels(ctx context.Context) ([]string, error) {
	url := strings.TrimRight(c.cfg.GetRouterURL(), "/")
	if strings.HasSuffix(url, "/chat/completions") {
		url = strings.TrimSuffix(url, "/chat/completions")
	}
	if !strings.HasSuffix(url, "/v1") && !strings.Contains(url, "/models") {
		url += "/v1"
	}
	if !strings.HasSuffix(url, "/models") {
		url += "/models"
	}

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}

	if apiKey := c.cfg.GetAPIKey(); apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 4<<10))
		return nil, fmt.Errorf("models API returned %d: %s", resp.StatusCode, string(body))
	}

	// routerUrl is user-configurable, so cap the response size (trust boundary).
	body, err := io.ReadAll(io.LimitReader(resp.Body, 10<<20))
	if err != nil {
		return nil, err
	}

	var raw struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}

	if err := json.Unmarshal(body, &raw); err != nil {
		return nil, err
	}

	var models []string
	for _, m := range raw.Data {
		if m.ID != "" {
			models = append(models, m.ID)
		}
	}

	return models, nil
}

// Complete sends a prompt and returns the full translated text with Auto-Retry
func (c *Client) Complete(ctx context.Context, systemPrompt, userPrompt, modelName string, temperature float64) (string, error) {
	if modelName == "" {
		modelName = c.cfg.GetDefaultModel()
	}
	if temperature <= 0 {
		temperature = c.cfg.GetTemperature()
	}

	reqPayload := ChatCompletionRequest{
		Model: modelName,
		Messages: []LLMMessage{
			{Role: "system", Content: systemPrompt},
			{Role: "user", Content: userPrompt},
		},
		Temperature: temperature,
		MaxTokens:   4096,
		Stream:      false,
	}

	jsonData, err := json.Marshal(reqPayload)
	if err != nil {
		return "", err
	}

	url := strings.TrimRight(c.cfg.GetRouterURL(), "/")
	if !strings.HasSuffix(url, "/v1") && !strings.Contains(url, "/chat/completions") {
		url += "/v1"
	}
	if !strings.HasSuffix(url, "/chat/completions") {
		url += "/chat/completions"
	}

	maxRetries := 3
	var lastErr error

	for attempt := 1; attempt <= maxRetries; attempt++ {
		select {
		case <-ctx.Done():
			return "", ctx.Err()
		default:
		}

		req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(jsonData))
		if err != nil {
			return "", err
		}

		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("HTTP-Referer", "http://localhost:4173")
		req.Header.Set("X-Title", "NovelClaw")
		if apiKey := c.cfg.GetAPIKey(); apiKey != "" {
			req.Header.Set("Authorization", "Bearer "+apiKey)
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("LLM request failed (attempt %d/%d): %w", attempt, maxRetries, err)
			if attempt < maxRetries {
				time.Sleep(time.Duration(attempt*1500) * time.Millisecond)
				continue
			}
			return "", lastErr
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			errMsg := fmt.Sprintf("LLM error (HTTP %d): %s", resp.StatusCode, string(body))
			lastErr = fmt.Errorf("%s", errMsg)
			// Retry on 429 (Rate Limit) or 5xx (Server error)
			if (resp.StatusCode == 429 || resp.StatusCode >= 500) && attempt < maxRetries {
				time.Sleep(time.Duration(attempt*2000) * time.Millisecond)
				continue
			}
			return "", lastErr
		}

		if err != nil {
			lastErr = fmt.Errorf("read response failed (attempt %d/%d): %w", attempt, maxRetries, err)
			if attempt < maxRetries {
				time.Sleep(time.Duration(attempt*1500) * time.Millisecond)
				continue
			}
			return "", lastErr
		}

		cleanBody := bytes.TrimSpace(body)
		if idx := bytes.Index(cleanBody, []byte("data: [DONE]")); idx != -1 {
			cleanBody = bytes.TrimSpace(cleanBody[:idx])
		}
		if start := bytes.IndexByte(cleanBody, '{'); start != -1 {
			if end := bytes.LastIndexByte(cleanBody, '}'); end != -1 && end > start {
				cleanBody = cleanBody[start : end+1]
			}
		}

		var chatResp ChatCompletionResponse
		if err := json.Unmarshal(cleanBody, &chatResp); err != nil {
			return "", fmt.Errorf("invalid response JSON: %w (body: %s)", err, string(body))
		}

		if chatResp.Error != nil {
			return "", fmt.Errorf("LLM API error: %s (%s)", chatResp.Error.Message, chatResp.Error.Type)
		}

		if len(chatResp.Choices) == 0 {
			return "", fmt.Errorf("empty choices in LLM response")
		}

		return chatResp.Choices[0].Message.Content, nil
	}

	return "", lastErr
}
