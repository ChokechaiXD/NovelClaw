package translator

import (
	"strings"
	"testing"
)

func TestSanitizeText_All20LeakedPatterns(t *testing.T) {
	cases := []struct {
		input    string
		hasHanzi bool
	}{
		{"แม้ว่าจะยังมีความเสี่ยงของการกบฏ แต่至少พวกเขาไม่คิดจะหนีตลอดเวลา", false},
		{"นักรบหมูป่าระดับที่สองมีพลังโจมตีมากกว่า 300 และเมื่อรวมกับ【祝福แห่งความกล้าหาญ】ของหลิวมู่ซือ", false},
		{"และคราวนี้การ突破จะยากขึ้นกว่าเดิม", false},
		{"ในหมู่ผู้ติดตามของเขา เช่น ซาร่า วอลลิแบร์ และเอลิซา มี至少หนึ่งโหลที่มีเลเวล 3", false},
		{"และผู้มีเลเวล 3 เหล่านี้ รวมถึงเฉาซิงและหลิวมู่เซว่ต้องการจะ突破ไปถึงเลเวล 4", false},
		{"หากต้องการให้ทหารอัสคารอนและนักรบหมูป่าทุกคนเพิ่มเลเวล 3 ต้องใช้สัญลักษณ์มังกรน้ำแข็ง至少 2 ล้านเหรียญ!", false},
		{"เฉาซิงรู้ว่า หากต้องการได้รับสัญลักษณ์มังกรน้ำแข็งจำนวนมากในเวลาสั้น ๆ ต้องไม่靠ตัวเองเพียงอย่างเดียว", false},
		{"当然 สิ่งนี้ต้องมีเงื่อนไขว่าพวกเขาต้องมีของที่น่าสนใจให้กับพวกเขา", false},
		{"เฉาซิงยิ้มและพูดว่า \"算了, เดินไปสักครู่ก่อน\"", false},
		{"\"ไม่ว่าจะเป็นอย่างไร หลังจากที่การ挑战มังกรยักษ์ครั้งนี้จบลง ฉันควรจะได้รับสัญลักษณ์มังกรน้ำแข็งจำนวนมาก\"", false},
		{"และ就在ขณะนั้น นักรบหมูป่าคนหนึ่งร้องขึ้นว่า \"ท่านลอร์ด! มีรังน้ำแข็งที่น่าสงสัยที่นี่\"", false},
		{"เมื่อมันปรากฏตัว มันก็发出เสียงคำรามเหมือนสัตว์ป่า", false},
		{"เสียงของสัตว์ป่า (การ发出เสียงคำรามที่น่ากลัว ทำให้สิ่งมีชีวิตในรังน้ำแข็งต่าง ๆ มีความเร็ว)", false},
		{"ในตอนนี้ ผู้รอดชีวิตจากหอ望江ได้พูดขึ้นอย่างรวดเร็วว่า \"ดูสิ เฉาซิงหนีไปพร้อมกับคนของเขา\"", false},
		{"ในตอนนี้ ผู้รอดชีวิตคนหนึ่งที่ชื่อ尹澤興ได้พูดขึ้นว่า \"คุณคิดว่ามีความเป็นไปได้หรือไม่\"", false},
		{"\"คุณคิดว่ามีคำอธิบายอื่นที่เป็นไปได้หรือไม่ ไม่ใช่เชื่อคำพูดของคนจากหอ望江\"", false},
		{"แต่除了คำอธิบายนี้แล้ว พวกเขาก็ไม่สามารถคิดคำอธิบายอื่นๆ ได้", false},
		{"\"ต้าไป๋ วอลลิแบร์ ซาร่า จงรวมตัวกันเป็นกลุ่มโจมตีและไปทำลายรังน้ำแข็งที่ไม่ได้孵พันธุ์สิ่งมีชีวิตอีกต่อไป\"", false},
		{"มีดที่ไม่มีเสียงเริ่ม划过อย่างไม่หยุดยั้ง", false},
		{"ผู้รอดชีวิตเห็น排名ของเฉาซิงที่พุ่งพรวดขึ้นไป และต่างตกใจโห่ร้อง!", false},
	}

	for i, tc := range cases {
		out := SanitizeText(tc.input, nil)
		if HasHanzi(out) != tc.hasHanzi {
			t.Errorf("Case %d failed: expected HasHanzi=%v, got out=%q", i+1, tc.hasHanzi, out)
		}
	}
}

func TestSanitizeText_CustomGlossaryPrecedence(t *testing.T) {
	custom := map[string]string{
		"曹星":   "เฉาซิงจอมราชัน",
		"曹星大人": "ท่านเฉาซิงผู้ยิ่งใหญ่",
	}

	// Longest match (曹星大人) should be replaced first over shorter (曹星)
	input := "ยินดีต้อนรับ 曹星大人 สู่ดินแดน"
	out := SanitizeText(input, custom)

	if !strings.Contains(out, "ท่านเฉาซิงผู้ยิ่งใหญ่") {
		t.Errorf("Expected longest match 'ท่านเฉาซิงผู้ยิ่งใหญ่', got %q", out)
	}
	if HasHanzi(out) {
		t.Errorf("Result still contains Hanzi: %q", out)
	}
}

func TestSanitizeParagraphs(t *testing.T) {
	paras := []string{
		"ย่อหน้าที่ 1 ไม่มีจีน",
		"ย่อหน้าที่ 2 มี 获得 พร",
		"ย่อหน้าที่ 3 มี 突破 ขั้น",
	}
	cleaned := SanitizeParagraphs(paras, nil)

	if len(cleaned) != 3 {
		t.Fatalf("Expected 3 paragraphs, got %d", len(cleaned))
	}
	for i, p := range cleaned {
		if HasHanzi(p) {
			t.Errorf("Paragraph %d still contains Hanzi: %q", i+1, p)
		}
	}
}

func TestSanitizeText_SingleHanziFallback(t *testing.T) {
	input := "มีมังกร 龍 และไฟ 火 และดาบ 劍"
	out := SanitizeText(input, nil)

	if HasHanzi(out) {
		t.Errorf("Expected zero Hanzi, got %q", out)
	}
	if !strings.Contains(out, "มังกร") || !strings.Contains(out, "ไฟ") || !strings.Contains(out, "ดาบ") {
		t.Errorf("Expected translated single words, got %q", out)
	}
}

func TestHasHanzi(t *testing.T) {
	if !HasHanzi("你好") {
		t.Error("Expected HasHanzi('你好') == true")
	}
	if HasHanzi("Hello World ภาษาไทย 123 !@#") {
		t.Error("Expected HasHanzi without Chinese to be false")
	}
}
