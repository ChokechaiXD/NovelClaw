package translator

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"novelclaw/internal/model"
)

// DiscoverGlossaryTerms analyzes novel text and extracts named entities (characters, places, skills, items)
func (c *Client) DiscoverGlossaryTerms(ctx context.Context, novelTitle string, sampleParagraphs []string, modelName string) ([]model.GlossaryItem, error) {
	if len(sampleParagraphs) == 0 {
		return []model.GlossaryItem{}, nil
	}

	// Limit sample text size to avoid context blowup (~1500 chars)
	var sampleText strings.Builder
	for _, p := range sampleParagraphs {
		if sampleText.Len() > 3000 {
			break
		}
		sampleText.WriteString(p)
		sampleText.WriteString("\n")
	}

	systemPrompt := `คุณคือผู้เชี่ยวชาญการตรวจวิเคราะห์ชื่อเฉพาะในนิยายจีน/อังกฤษเพื่อสร้างตารางศัพท์แปลไทย (Glossary)
หน้าที่ของคุณคือ: สกัด "ชื่อตัวละคร, สถานที่, วิชา/ระดับพลัง, กลุ่ม/สำนัก, และไอเทมสำคัญ" จากข้อความต้นฉบับ พร้อมเสนอคำทับศัพท์หรือคำแปลภาษาไทยที่ถูกต้องตามหลักการแปลวรรณกรรม

ข้อกำหนดสำคัญ:
- ตอบกลับในรูปแบบ JSON Array เท่านั้น (ไม่มีคำทักทาย ไม่มีคำอธิบายเพิ่มเติม)
- ตัวอย่างรูปแบบ:
[
  {"term": "曹星", "target": "เฉาซิง", "category": "character", "notes": "ตัวเอก"},
  {"term": "柳慕雪", "target": "หลิวมู่เสวี่ย", "category": "character", "notes": "พี่สะใภ้"},
  {"term": "冰封纪元", "target": "ยุคน้ำแข็ง", "category": "custom", "notes": "ชื่อเกม/โลก"}
]`

	userPrompt := fmt.Sprintf("ชื่อเรื่อง: %s\n\n[ข้อความต้นฉบับ]\n%s", novelTitle, sampleText.String())

	reqCtx, cancel := context.WithTimeout(ctx, 90*time.Second)
	defer cancel()

	rawOutput, err := c.Complete(reqCtx, systemPrompt, userPrompt, modelName, 0.1)
	if err != nil {
		return nil, fmt.Errorf("entity discovery error: %w", err)
	}

	return parseGlossaryJSON(rawOutput), nil
}

func parseGlossaryJSON(raw string) []model.GlossaryItem {
	raw = strings.TrimSpace(raw)
	// Strip markdown code block
	if strings.HasPrefix(raw, "```") {
		idx := strings.Index(raw, "\n")
		if idx != -1 {
			raw = raw[idx+1:]
		}
		if lastIdx := strings.LastIndex(raw, "```"); lastIdx != -1 {
			raw = raw[:lastIdx]
		}
		raw = strings.TrimSpace(raw)
	}

	var items []model.GlossaryItem
	if err := json.Unmarshal([]byte(raw), &items); err == nil {
		return items
	}

	// Try extracting from substring starting with '[' and ending with ']'
	start := strings.Index(raw, "[")
	end := strings.LastIndex(raw, "]")
	if start != -1 && end != -1 && end > start {
		sub := raw[start : end+1]
		_ = json.Unmarshal([]byte(sub), &items)
	}

	return items
}
