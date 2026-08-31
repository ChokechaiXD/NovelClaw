package translator

import "testing"

func TestFindMissingNumbers(t *testing.T) {
	tests := []struct {
		name               string
		source, translated []string
		wantMissing        []string
	}{
		{
			name:        "thousands separator normalizes",
			source:      []string{"总人口达到了38024人"},
			translated:  []string{"ประชากรรวมถึง 38,024 คน"},
			wantMissing: []string{},
		},
		{
			name:        "reordered game values pass",
			source:      []string{"打爆后会出现3~8只3级小魔蛛"},
			translated:  []string{"จะมีลูกแมงมุมเลเวล 3 ปรากฏ 3-8 ตัว"},
			wantMissing: []string{},
		},
		{
			name:        "chinese numeral conversion passes",
			source:      []string{"在接下来的六小时时间里，方圆30公里"},
			translated:  []string{"ภายในเวลา 6 ชั่วโมง รัศมี 30 กิโลเมตร"},
			wantMissing: []string{},
		},
		{
			name:        "genuinely vanished number is flagged",
			source:      []string{"他等了30分钟"},
			translated:  []string{"เขารอมานานหลายสิบนาที"},
			wantMissing: []string{"30"},
		},
		{
			name:        "repeated tokens count individually",
			source:      []string{"损失3只 3只 3只"},
			translated:  []string{"เสีย 3 ตัว 3 ตัว"},
			wantMissing: []string{"3"},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := findMissingNumbers(tc.source, tc.translated)
			if len(got) != len(tc.wantMissing) {
				t.Fatalf("missing = %v, want %v", got, tc.wantMissing)
			}
			for i := range got {
				if got[i] != tc.wantMissing[i] {
					t.Fatalf("missing = %v, want %v", got, tc.wantMissing)
				}
			}
		})
	}
}

func TestEvaluateTranslationQualityNumberCheck(t *testing.T) {
	// The real-world false positive: "38,024" vs "38024" used to drop 10 points.
	rep := EvaluateTranslationQuality("n", 1, []string{"总人口38024人"}, []string{"ประชากร 38,024 คน"}, nil)
	for _, iss := range rep.Issues {
		if iss.Code == "number_mismatch" {
			t.Fatalf("comma-normalized numbers must not flag: %+v", rep.Issues)
		}
	}
}
