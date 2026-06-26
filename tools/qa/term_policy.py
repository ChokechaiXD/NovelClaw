"""tools/qa/term_policy.py — Term Action Registry loader + resolver.

Loads term_policy.th.yaml, normalizes tokens, resolves actions.
Replaces the mixed allowlist/blacklist/replacement approach with
a single registry per target language.

Usage:
    from qa.term_policy import TermPolicy

    tp = TermPolicy.load("th")
    result = tp.apply_to_text("ได้รับ Elite Totem แล้ว")
    # → "ได้รับ อีลิท โทเทม แล้ว"
    # result.replaced: {"Elite": "อีลิท", "totem": "โทเทม"}
    # result.preserved: set()
    # result.unknown: set()
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


# ── Data types ────────────────────────────────────────────────────────

@dataclass
class TermAction:
    """Single term entry from policy."""
    token: str          # Canonical form (lowercase for case-insensitive match)
    display_token: str  # Original form as written in YAML
    action: str         # replace | preserve | review | fail
    value: str | None   # Thai replacement (only for replace)
    category: str = ""


@dataclass
class ApplyResult:
    """Result of applying term policy to text."""
    text: str
    replaced: dict[str, str] = field(default_factory=dict)
    preserved: set[str] = field(default_factory=set)
    soft_allowed: set[str] = field(default_factory=set)
    reviewed: list[str] = field(default_factory=list)
    unknown_foreign: list[str] = field(default_factory=list)


@dataclass
class TermPolicy:
    """Term action registry for a target language."""
    target_lang: str
    default_action: str = "fail"
    terms: dict[str, TermAction] = field(default_factory=dict)
    preserve_patterns: dict[str, list[re.Pattern]] = field(default_factory=dict)
    _phrase_pattern: re.Pattern | None = None

    @property
    def preserve_tokens(self) -> set[str]:
        """Set of tokens with preserve action (cased as in YAML)."""
        return {t.display_token for t in self.terms.values() if t.action == "preserve"}

    @classmethod
    def load(cls, target_lang: str = "th") -> "TermPolicy":
        """Load term policy from YAML config."""
        cfg_path = _find_config(target_lang)
        if cfg_path:
            return _load_yaml(cfg_path, target_lang)
        return TermPolicy(target_lang=target_lang)

    def apply_to_text(self, text: str) -> ApplyResult:
        """Apply term actions to a text string.
        
        Order: phrase replacement first, then per-token check.
        Returns modified text and action reports.
        """
        result = ApplyResult(text=text)

        # Phase 1: Phrase-level replacement (multi-word tokens)
        if self._phrase_pattern:
            def _replace_phrase(m: re.Match) -> str:
                matched = m.group(0)
                key = matched.lower()
                term = self.terms.get(key)
                if term and term.action == "replace" and term.value:
                    result.replaced[matched] = term.value
                    return term.value
                if term and term.action == "preserve":
                    result.preserved.add(matched)
                return matched
            result.text = self._phrase_pattern.sub(_replace_phrase, result.text)

        # Phase 2: Pattern-based preservation (before per-word check)
        if self.preserve_patterns:
            tokens_found = list(set(re.findall(r"\b([A-Za-z][A-Za-z0-9.]*)\b", result.text)))
            for token in tokens_found:
                for pattern_name, patterns in self.preserve_patterns.items():
                    for pat in patterns:
                        if pat.search(token):
                            result.preserved.add(token)
                            # script_policy does .upper() check, add uppercase variant
                            result.preserved.add(token.upper())
                            break

        # Phase 3: Per-word token resolution
        tokens_found = set(re.findall(r"\b([A-Za-z][A-Za-z0-9.]*)\b", result.text))
        for token in tokens_found:
            # Skip if already preserved by pattern
            if token in result.preserved:
                continue
            key = token.lower()
            term = self.terms.get(key)
            if term:
                if term.action == "replace" and term.value:
                    # Word-level replace
                    old_text = result.text
                    result.text = re.sub(rf"\b{re.escape(token)}\b", term.value, result.text)
                    if old_text != result.text:
                        result.replaced[token] = term.value
                elif term.action == "preserve":
                    result.preserved.add(token)
                elif term.action == "soft_allow":
                    result.soft_allowed.add(token)
                elif term.action == "review":
                    result.reviewed.append(token)
            else:
                # Unknown foreign token
                result.unknown_foreign.append(token)

        return result


# ── Helpers ───────────────────────────────────────────────────────────

def _find_config(target_lang: str) -> Path | None:
    """Find config/term_policy.{lang}.yaml in project directories."""
    candidates = [
        Path(__file__).resolve().parent.parent / "config" / f"term_policy.{target_lang}.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_yaml(path: Path, target_lang: str) -> TermPolicy:
    """Load YAML config (pure Python, no PyYAML dependency)."""
    text = path.read_text(encoding="utf-8")
    
    # Simple YAML parser — only supports the structure we need
    import re as _re
    
    policy = TermPolicy(target_lang=target_lang)
    
    # Default action
    m = _re.search(r"^\s*unknown_foreign_script:\s*(\w+)", text, _re.MULTILINE)
    if m:
        policy.default_action = m.group(1)
    
    # Parse terms block
    current_token = None
    current_action = {}
    in_terms = False
    
    for line in text.split("\n"):
        stripped = line.strip()
        
        if stripped.startswith("terms:"):
            in_terms = True
            continue
        
        if not in_terms:
            continue
        
        if not stripped or stripped.startswith("#"):
            continue
        
        # Token key (2-space indent)
        m = _re.match(r"^  ([A-Za-z0-9 _.-]+):$", line)
        if m:
            if current_token and current_action:
                _register_term(policy, current_token, current_action)
            current_token = m.group(1).strip()
            current_action = {}
            continue
        
        # Property (4-space indent under token)
        m = _re.match(r"^\s{4,}(\w+):\s*(.*)", line)
        if m and current_token:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            current_action[key] = val
    
    # Save last
    if current_token and current_action:
        _register_term(policy, current_token, current_action)
    
    # Load preserve patterns
    m = _re.search(r"preserve_patterns:\n", text)
    if m:
        current_group = None
        for line in text.split("\n"):
            stripped = line.strip()
            
            # Group header (e.g. "  level_notation:")
            m_group = _re.match(r"^\s{2}(\w+):\s*$", line)
            if m_group:
                current_group = m_group.group(1)
                if current_group not in policy.preserve_patterns:
                    policy.preserve_patterns[current_group] = []
                continue
            
            # Pattern line (e.g. "    - '\bLV\.?\s*\d+\b'")
            m_pat = _re.match(r"^\s{4}-\s+'(.+)'$", line)
            if m_pat and current_group:
                try:
                    compiled = _re.compile(m_pat.group(1), _re.IGNORECASE)
                    policy.preserve_patterns[current_group].append(compiled)
                except _re.error:
                    pass
    
    # Build phrase pattern for multi-word tokens
    multi_word = [t for k, t in policy.terms.items() if " " in t.display_token]
    if multi_word:
        phrases = sorted([t.display_token for t in multi_word], key=len, reverse=True)
        escaped = [re.escape(p) for p in phrases]
        policy._phrase_pattern = re.compile("|".join(escaped), re.IGNORECASE)
    
    return policy


def _register_term(policy: TermPolicy, token: str, action: dict):
    """Register a term in the policy."""
    key = token.lower()
    act = action.get("action", "review")
    val = action.get("value")
    cat = action.get("category", "")
    
    if act not in ("replace", "preserve", "review", "fail"):
        act = "review"
    
    policy.terms[key] = TermAction(
        token=key,
        display_token=token,
        action=act,
        value=val,
        category=cat,
    )


# ── Convenience ───────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def get_term_policy(target_lang: str = "th") -> TermPolicy:
    """Cached loader."""
    return TermPolicy.load(target_lang)
