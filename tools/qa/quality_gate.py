"""tools/qa/quality_gate.py — Consolidated translation quality gate.

Replaces the scattered validate/score/check approach with a single gate
that runs ALL checks in order and returns a single pass/fail verdict.

Order of operations:
  1. Normalize output
  2. Smart paragraph segmentation
  3. Apply term actions (replace before check)
  4. Script purity check (with preserved tokens from term policy)
  5. Thai style lint
  6. Structure/completeness check
  7. Final verdict

Usage:
    from qa.quality_gate import quality_gate

    result = quality_gate(ch_data, source_text, mode="production")
    if result.ok:
        save_canonical(...)
    elif result.retry:
        retry_with_quality_model(...)
    else:
        save_needs_review(...)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa.term_policy import get_term_policy, ApplyResult
from qa.script_policy import detect_script_leaks, format_leak_report


# ── Gate modes ───────────────────────────────────────────────────────

GATE_MODES = {
    "production": {
        "Latin": "fail",
        "Han": "fail",
        "Hiragana": "fail",
        "Katakana": "fail",
        "Hangul": "fail",
        "Cyrillic": "fail",
        "Arabic": "fail",
        "style_issue": "warning",
    },
    "draft": {
        "Latin": "warning",
        "Han": "fail",
        "Hiragana": "fail",
        "Katakana": "fail",
        "Hangul": "fail",
        "Cyrillic": "fail",
        "Arabic": "fail",
        "style_issue": "warning",
    },
    "debug": {
        "Latin": "warning",
        "Han": "warning",
        "Hiragana": "warning",
        "Katakana": "warning",
        "Hangul": "warning",
        "Cyrillic": "warning",
        "Arabic": "warning",
        "style_issue": "info",
    },
}


# ── Data types ───────────────────────────────────────────────────────

@dataclass
class GateResult:
    """Result of running the quality gate on a chapter."""
    ok: bool = False
    retry: bool = False
    needs_review: bool = False
    score: float = 100.0
    paragraphs: list[str] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    reports: dict = field(default_factory=dict)


# ── Smart paragraph segmentation ─────────────────────────────────────

def _smart_segment(paragraphs: list[str]) -> list[str]:
    """Split paragraphs that contain inline newlines (Gemma pattern).
    
    If a paragraph has \n and the chapter has very few paragraphs (< 10),
    try splitting by \n and check if we get plausible paragraphs.
    """
    result = []
    for p in paragraphs:
        if "\n" in p and len(p) > 500:
            parts = [s.strip() for s in p.split("\n") if s.strip()]
            long_parts = [pt for pt in parts if len(pt) > 30]
            if len(long_parts) >= 3:
                result.extend(long_parts)
            else:
                result.append(p)
        else:
            result.append(p)
    return result


# ── Thai style lint ──────────────────────────────────────────────────

def _lint_thai_style(paragraphs: list[str]) -> list[dict]:
    """Check Thai style quality.
    
    Returns list of issues.
    """
    issues = []
    non_end = [p for p in paragraphs if p != "(จบบท)"]
    
    if not non_end:
        return issues
    
    # "ก็" density
    go_count = sum(1 for p in non_end if "ก็" in p)
    go_pct = go_count / len(non_end) * 100
    if go_pct > 35:
        issues.append({
            "type": "style",
            "severity": "warning",
            "message": f"\"ก็\" density {go_pct:.0f}% > 35% ({go_count}/{len(non_end)})",
        })
    
    # Short fragment analysis
    short = sum(1 for p in non_end if len(p) < 30)
    short_pct = short / len(non_end) * 100
    if short_pct > 40 and len(non_end) > 50:
        issues.append({
            "type": "style",
            "severity": "info",
            "message": f"Short paragraphs (<30 chars) {short_pct:.0f}% ({short}/{len(non_end)})",
        })
    
    return issues


# ── Structure check ──────────────────────────────────────────────────

def _check_structure(paragraphs: list[str], source_text: str | None) -> list[dict]:
    """Check basic structure requirements."""
    issues = []
    non_end = [p for p in paragraphs if p != "(จบบท)"]
    
    if not non_end:
        issues.append({"type": "structure", "severity": "error", "message": "No paragraphs"})
        return issues
    
    # End marker
    if not paragraphs or paragraphs[-1] not in ("(จบบท)", "(End)", "（終）", "(끝)"):
        issues.append({"type": "structure", "severity": "error", "message": "Missing end marker"})
    
    # Empty paragraphs
    empty = sum(1 for p in non_end if not p.strip())
    if empty > 0:
        issues.append({
            "type": "structure",
            "severity": "warning",
            "message": f"{empty} empty paragraphs",
        })
    
    return issues


# ── Main gate ────────────────────────────────────────────────────────

@dataclass
class QualityGate:
    """Configured quality gate ready to run."""
    mode: str = "production"
    target_lang: str = "th"
    term_policy: Any = None  # TermPolicy
    
    def run(self, paragraphs: list[str], source_text: str | None = None) -> GateResult:
        """Run the quality gate on chapter paragraphs.
        
        Returns GateResult with pass/fail and detailed reports.
        """
        result = GateResult()
        mode_config = GATE_MODES.get(self.mode, GATE_MODES["production"])
        score = 100.0
        
        # 1. Smart segmentation
        segmented = _smart_segment(paragraphs)
        result.paragraphs = segmented
        
        # 2. Term actions (replace before check)
        tp = self.term_policy or get_term_policy(self.target_lang)
        term_result = ApplyResult(text="")
        # Apply term actions to each paragraph
        applied_paras = []
        for p in segmented:
            tr = tp.apply_to_text(p)
            applied_paras.append(tr.text)
            term_result.replaced.update(tr.replaced)
            term_result.preserved.update(tr.preserved)
            term_result.unknown_foreign.extend(tr.unknown_foreign)
        result.paragraphs = applied_paras
        result.reports["terms"] = {
            "replaced": dict(term_result.replaced),
            "preserved": list(term_result.preserved),
            "unknown_foreign": term_result.unknown_foreign,
        }
        
        # Deduct for unknown foreign terms
        # soft_allowed terms = info severity, 0 deduction
        for token in term_result.soft_allowed:
            result.issues.append({
                "type": "script",
                "severity": "info",
                "message": f"Soft-allowed token: {token} (review later)",
            })

        for token in term_result.unknown_foreign:
            severity = mode_config.get("unknown_latin", "warning")
            if severity == "fail":
                score -= 10
                result.issues.append({
                    "type": "script",
                    "severity": "error",
                    "message": f"Unknown foreign token: {token}",
                })
            elif severity == "warning":
                score -= 3
                result.issues.append({
                    "type": "script",
                    "severity": "warning",
                    "message": f"Unknown foreign token: {token}",
                })
        
        # Source artifact check
        from qa.validators import SOURCE_ARTIFACT_RE
        for idx, p in enumerate(result.paragraphs):
            match = SOURCE_ARTIFACT_RE.search(p)
            if match:
                score -= 15
                result.issues.append({
                    "type": "artifact",
                    "severity": "error",
                    "message": f"Source artifact detected: '{match.group(1)}' in paragraph {idx + 1}",
                })

        # 3. Script purity
        preserve_set = set(term_result.preserved) | tp.preserve_tokens
        from qa.script_policy import TARGET_SCRIPT_POLICY
        policy = TARGET_SCRIPT_POLICY.get(self.target_lang, {})
        allowed_scripts = policy.get("allowed_scripts", set())
        hard_fail_scripts = policy.get("hard_fail_scripts", set())
        
        script_leaks = detect_script_leaks(
            result.paragraphs,
            target_lang=self.target_lang,
            allowed_latin_tokens=preserve_set,
        )
        result.reports["script"] = {
            "leaks": [f"{l.script}:{l.token}" for l in script_leaks.leaks],
            "clean": len(script_leaks.leaks) == 0,
        }
        
        for leak in script_leaks.leaks:
            sev = mode_config.get(leak.script, "warning")
            script_display = leak.script
            if leak.script in ("Han", "Hiragana", "Katakana", "Hangul"):
                script_display = f"CJK ({leak.script})"

            if sev == "fail":
                score -= 20
                result.issues.append({
                    "type": "script",
                    "severity": "error",
                    "message": f"{script_display} leak: '{leak.token}' at pos {leak.index}",
                })
            elif sev == "warning":
                score -= 5
                result.issues.append({
                    "type": "script",
                    "severity": "warning",
                    "message": f"{script_display} leak: '{leak.token}'",
                })
        
        # 3.5 CJK Punctuation check
        from qa.validators import CJK_PUNCT_RE
        for idx, p in enumerate(result.paragraphs):
            # Skip end markers
            if p in ("(จบบท)", "(End)", "（終）", "(끝)"):
                continue
            matches = CJK_PUNCT_RE.findall(p)
            if matches:
                unique_matches = sorted(list(set(matches)))
                for m in unique_matches:
                    if m in ("「", "」"):
                        score -= 15
                        result.issues.append({
                            "type": "cjk_punctuation",
                            "severity": "error",
                            "message": f"CJK quotation mark '{m}' detected in paragraph {idx + 1}. Use standard double quotes '\"'.",
                        })
                    else:
                        score -= 5
                        result.issues.append({
                            "type": "cjk_punctuation",
                            "severity": "warning",
                            "message": f"CJK punctuation/bracket '{m}' leaked in paragraph {idx + 1}. Clean or replace with standard punctuation.",
                        })

        # 4. Thai style lint
        style_issues = _lint_thai_style(result.paragraphs)
        for si in style_issues:
            if si["severity"] == "warning":
                score -= 5
            result.issues.append(si)
        result.reports["style"] = style_issues
        
        # 5. Structure check
        struct_issues = _check_structure(result.paragraphs, source_text)
        for si in struct_issues:
            if si["severity"] == "error":
                score -= 15
            elif si["severity"] == "warning":
                score -= 3
            result.issues.append(si)
        result.reports["structure"] = struct_issues
        
        # Final verdict
        result.score = max(0.0, min(100.0, score))
        has_errors = any(i["severity"] == "error" for i in result.issues)
        has_warnings = any(i["severity"] == "warning" for i in result.issues)
        has_infos = any(i["severity"] == "info" for i in result.issues)
        
        if has_errors:
            if self.mode == "production":
                result.needs_review = True
                result.retry = score >= 50  # If score >= 50, worth retrying
            else:
                result.needs_review = True
        else:
            result.ok = True
        
        # Tag on info-only issues for reports
        result.reports["info_only"] = has_infos and not has_errors and not has_warnings
        
        return result


def quality_gate(
    paragraphs: list[str],
    source_text: str | None = None,
    mode: str = "production",
    target_lang: str = "th",
) -> GateResult:
    """Convenience function: create gate, run, return result."""
    gate = QualityGate(mode=mode, target_lang=target_lang)
    gate.term_policy = get_term_policy(target_lang)
    return gate.run(paragraphs, source_text)
