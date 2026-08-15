package translator

import (
	"sort"
	"strings"
	"unicode"
)

// HasHanzi reports whether s contains any Chinese (Han) characters
func HasHanzi(s string) bool {
	for _, r := range s {
		if unicode.Is(unicode.Han, r) {
			return true
		}
	}
	return false
}

// BuiltinNovelGlossary contains comprehensive Chinese novel vocabulary,
// gaming terms, stat keywords, and frequent leaks that LLMs fail to translate.
var BuiltinNovelGlossary = map[string]string{
	// Status & System Prompts
	"【获得：":   "【ได้รับ: ",
	"【獲得：":   "【ได้รับ: ",
	"【提示：":   "【การแจ้งเตือน: ",
	"【系统提示：": "【การแจ้งเตือนจากระบบ: ",
	"【系統提示：": "【การแจ้งเตือนจากระบบ: ",
	"【击杀：":   "【สังหาร: ",
	"【擊殺：":   "【สังหาร: ",
	"【祝福แห่งความกล้าหาญ】": "【พรแห่งความกล้าหาญ】",

	// Common leaked novel words
	"至少":    "อย่างน้อย",
	"祝福":    "พร",
	"突破":    "ทะลวงขั้น",
	"当然":    "แน่นอนว่า",
	"當然":    "แน่นอนว่า",
	"算了":    "ช่างเถอะ",
	"挑战":    "การท้าทาย",
	"挑戰":    "การท้าทาย",
	"就在":    "และใน",
	"发出":    "เปล่ง",
	"發出":    "เปล่ง",
	"除了":    "นอกเหนือจาก",
	"划过":    "กรีดผ่าน",
	"劃過":    "กรีดผ่าน",
	"排名":    "อันดับ",
	"击杀":    "สังหาร",
	"擊殺":    "สังหาร",
	"获得":    "ได้รับ",
	"獲得":    "ได้รับ",
	"提示":    "การแจ้งเตือน",
	"属性":    "ค่าสถานะ",
	"力量":    "พละกำลัง",
	"敏捷":    "ความว่องไว",
	"体质":    "สมรรถภาพร่างกาย",
	"體質":    "สมรรถภาพร่างกาย",
	"精神":    "พลังจิต",
	"技能":    "ทักษะ",
	"等级":    "เลเวล",
	"等級":    "เลเวล",
	"经验":    "ค่าประสบการณ์",
	"經驗":    "ค่าประสบการณ์",
	"装备":    "อุปกรณ์สวมใส่",
	"裝備":    "อุปกรณ์สวมใส่",
	"首领":    "จ่าฝูง",
	"首領":    "จ่าฝูง",
	"统领":    "ผู้บัญชาการ",
	"統領":    "ผู้บัญชาการ",
	"队长":    "หัวหน้าหน่วย",
	"隊長":    "หัวหน้าหน่วย",
	"积分":    "คะแนนสะสม",
	"積分":    "คะแนนสะสม",
	"忠诚度":   "ค่าความภักดี",
	"忠誠度":   "ค่าความภักดี",
	"天赋":    "พรสวรรค์",
	"天賦":    "พรสวรรค์",
	"领地":    "ดินแดน",
	"領地":    "ดินแดน",
	"领主":    "ท่านลอร์ด",
	"領主":    "ท่านลอร์ด",
	"领民":    "ประชากรในดินแดน",
	"領民":    "ประชากรในดินแดน",
	"深渊":    "เหวลึก",
	"深淵":    "เหวลึก",
	"怪物":    "สัตว์ประหลาด",
	"冰巢":    "รังน้ำแข็ง",
	"冰封纪元":  "ยุคน้ำแข็ง",
	"冰封紀元":  "ยุคน้ำแข็ง",
	"永恒之力":  "พลังแห่งนิรันดร์",
	"冰龙号角":  "เขามังกรน้ำแข็ง",
	"大嫂":    "พี่สะใภ้",
	"可惜":    "น่าเสียดายที่",
	"有挂":    "โกง",
	"超級":    "โคตร",
	"超级":    "โคตร",
	"只能":    "ทำได้แค่",
	"据官方所说": "ตามที่ทางการระบุไว้",
	"據官方所說": "ตามที่ทางการระบุไว้",

	// Proper Names & Organizations
	"望江":   "ว่างเจียง",
	"尹泽兴":  "อิ่นเจ๋อซิ่ง",
	"尹澤興":  "อิ่นเจ๋อซิ่ง",
	"江青云":  "เจียงชิงอวิ๋น",
	"江青雲":  "เจียงชิงอวิ๋น",
	"曹星":   "เฉาซิง",
	"曹一":   "เฉาอี้",
	"大白":   "ต้าไป๋",
	"莎拉":   "ซาร่า",
	"沃利贝尔": "วอลลิแบร์",
	"埃丽莎":  "เอลิซา",
	"柳慕雪":  "หลิวมู่เสวี่ย",
	"永盛集团": "หย่งเซิ่งกรุ๊ป",
	"永盛集團": "หย่งเซิ่งกรุ๊ป",
	"吴家辉":  "อู๋เจียฮุย",
	"吳家輝":  "อู๋เจียฮุย",
	"阿星":   "อาซิง",
	"香江":   "ฮ่องกง",
	"迈巴赫":  "มายบัค",
	"邁巴赫":  "มายบัค",
	"阿斯卡隆": "อัสคารอน",
	"野猪人":  "มนุษย์หมูป่า",
	"霜狼":   "หมาป่าเหมันต์",
}

// SingleHanziFallback translates any stray single Hanzi characters
var SingleHanziFallback = map[rune]string{
	'的': "ของ",
	'了': "แล้ว",
	'在': "ที่",
	'是': "คือ",
	'我': "ฉัน",
	'你': "นาย",
	'他': "เขา",
	'她': "เธอ",
	'它': "มัน",
	'不': "ไม่",
	'有': "มี",
	'没': "ไม่มี",
	'沒': "ไม่มี",
	'人': "คน",
	'大': "ใหญ่",
	'小': "เล็ก",
	'死': "ตาย",
	'生': "เกิด",
	'天': "วัน",
	'地': "ดิน",
	'心': "ใจ",
	'手': "มือ",
	'眼': "ตา",
	'头': "หัว",
	'頭': "หัว",
	'剑': "ดาบ",
	'劍': "ดาบ",
	'刀': "มีด",
	'枪': "ปืน",
	'槍': "ปืน",
	'龙': "มังกร",
	'龍': "มังกร",
	'火': "ไฟ",
	'冰': "น้ำแข็ง",
	'雪': "หิมะ",
	'水': "น้ำ",
	'金': "ทอง",
	'木': "ไม้",
	'土': "ดิน",
	'神': "เทพ",
	'魔': "มาร",
	'仙': "เซียน",
	'妖': "ปีศาจ",
	'鬼': "ผี",
	'王': "ราชา",
	'皇': "จักรพรรดิ",
	'门': "ประตู",
	'門': "ประตู",
	'城': "เมือง",
	'国': "ประเทศ",
	'國': "ประเทศ",
	'山': "ภูเขา",
	'海': "ทะเล",
	'风': "ลม",
	'風': "ลม",
	'雷': "สายฟ้า",
	'光': "แสง",
	'暗': "ความมืด",
	'夜': "กลางคืน",
	'日': "กลางวัน",
	'月': "ดวงจันทร์",
	'星': "ดวงดาว",
	'云': "เมฆ",
	'雲': "เมฆ",
	'雨': "ฝน",
	'靠': "พึ่งพา",
	'孵': "ฟัก",
	'过': "ผ่าน",
	'過': "ผ่าน",
	'划': "กรีด",
	'劃': "กรีด",
	'排': "จัด",
	'名': "ชื่อ",
	'发': "ส่ง",
	'發': "ส่ง",
	'出': "ออก",
	'破': "ทำลาย",
	'战': "ต่อสู้",
	'戰': "ต่อสู้",
	'福': "พร",
	'祝': "อวยพร",
	'突': "ทะลวง",
	'少': "น้อย",
	'至': "ถึง",
	'算': "คำนวณ",
	'当': "เป็น",
	'當': "เป็น",
	'然': "แน่นอน",
	'江': "แม่น้ำ",
	'望': "มอง",
	'挑': "ท้า",
	'除': "เว้น",
	'興': "เจริญ",
	'兴': "เจริญ",
	'澤': "สระ",
	'泽': "สระ",
	'尹': "อิ่น",
}

// Pre-sorted builtin glossary (longest terms first, computed once at startup)
type glossaryEntry struct {
	term string
	repl string
}

var sortedBuiltinGlossary []glossaryEntry

func init() {
	sortedBuiltinGlossary = make([]glossaryEntry, 0, len(BuiltinNovelGlossary))
	for k, v := range BuiltinNovelGlossary {
		sortedBuiltinGlossary = append(sortedBuiltinGlossary, glossaryEntry{term: k, repl: v})
	}
	sort.Slice(sortedBuiltinGlossary, func(i, j int) bool {
		return len(sortedBuiltinGlossary[i].term) > len(sortedBuiltinGlossary[j].term)
	})
}

// SanitizeText removes/replaces all Hanzi characters from text using dictionary & fallback rules.
func SanitizeText(text string, customGlossary map[string]string) string {
	if text == "" || !HasHanzi(text) {
		return text
	}

	result := text

	// 1. Custom/Novel Glossary Replacement (Longest terms first)
	if len(customGlossary) > 0 {
		type kv struct {
			k string
			v string
		}
		var list []kv
		for k, v := range customGlossary {
			list = append(list, kv{k: k, v: v})
		}
		sort.Slice(list, func(i, j int) bool {
			return len(list[i].k) > len(list[j].k)
		})
		for _, item := range list {
			if item.k != "" && strings.Contains(result, item.k) {
				result = strings.ReplaceAll(result, item.k, item.v)
			}
		}
	}

	if !HasHanzi(result) {
		return result
	}

	// 2. Builtin Comprehensive Multi-Character Novel Glossary (pre-sorted, longest first)
	for _, item := range sortedBuiltinGlossary {
		if strings.Contains(result, item.term) {
			result = strings.ReplaceAll(result, item.term, item.repl)
		}
	}

	if !HasHanzi(result) {
		return result
	}

	// 3. Fallback for stray single Chinese characters
	var b strings.Builder
	for _, r := range result {
		if unicode.Is(unicode.Han, r) {
			if trans, ok := SingleHanziFallback[r]; ok {
				b.WriteString(trans)
			}
			// If not in single fallback table, silently strip so zero Chinese characters leak
		} else {
			b.WriteRune(r)
		}
	}

	return b.String()
}

// SanitizeParagraphs cleans all paragraphs and returns a guaranteed 0-Hanzi list.
func SanitizeParagraphs(paragraphs []string, customGlossary map[string]string) []string {
	cleaned := make([]string, 0, len(paragraphs))
	for _, p := range paragraphs {
		sanitized := SanitizeText(p, customGlossary)
		cleaned = append(cleaned, sanitized)
	}
	return cleaned
}
