"""translation_memory.py — Block-level translation cache (L1 exact + L2 fuzzy).

Architecture:
  L1 (Exact): hash(block_text) → translation → O(1) lookup
  L2 (Fuzzy): Jaccard similarity on character bigrams ≥ 0.85 → reuse

No external ML dependencies — pure Python set operations.
Character bigram Jaccard is surprisingly effective for CN/TH text
where word boundaries are ambiguous.

Storage: .tmemory/<slug>.json (simple, portable, diffable)

Flow:
  1. Before LLM call, check TM for each source block
  2. L1: hash match → reuse translation immediately
  3. L2: Jaccard ≥ 0.85 → reuse translation (with warning)
  4. After LLM call, cache new translations back to TM
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

# ── Config ────────────────────────────────────────────────────────────
JACCARD_THRESHOLD = 0.85  # Cosine/Jaccard threshold for fuzzy match
TM_DIR_NAME = ".tmemory"
MAX_FUZZY_CANDIDATES = 50  # Only scan this many candidates for fuzzy match
MAX_BLOCK_LEN = 500  # Don't cache blocks longer than this


# ── Helpers ──────────────────────────────────────────────────────────

def _bigrams(text: str) -> set[str]:
    """Generate character bigrams (2-char sliding window)."""
    return {text[i:i+2] for i in range(len(text) - 1)}


def _block_hash(text: str) -> str:
    """SHA-256 hash of block text, first 16 hex chars."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clean_block(text: str) -> str:
    """Normalize block text for comparison — strip quotes, whitespace.
    
    This helps fuzzy matching match blocks that differ only in
    punctuation or whitespace.
    """
    cleaned = text.strip()
    # Strip common quote pairs
    for pair in ['""', '""', '「」', '""', '()', '（）']:
        if len(pair) == 2 and cleaned.startswith(pair[0]) and cleaned.endswith(pair[1]):
            cleaned = cleaned[1:-1].strip()
    return cleaned


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity on character bigrams.
    
    Jaccard = |intersection| / |union|
    Range: 0.0 (no overlap) to 1.0 (identical bigram sets)
    """
    bigrams_a = _bigrams(text_a)
    bigrams_b = _bigrams(text_b)
    if not bigrams_a or not bigrams_b:
        return 0.0
    intersection = bigrams_a & bigrams_b
    union = bigrams_a | bigrams_b
    return len(intersection) / len(union)


def length_ratio_ok(text_a: str, text_b: str, min_ratio: float = 0.5, max_ratio: float = 2.0) -> bool:
    """Check if lengths are compatible for fuzzy matching."""
    if not text_a or not text_b:
        return False
    ratio = len(text_a) / len(text_b)
    return min_ratio <= ratio <= max_ratio


# ── TM Storage ────────────────────────────────────────────────────────

class TranslationMemory:
    """Block-level translation cache.
    
    Structure:
      .tmemory/<slug>.json = {
        "meta": {},
        "exact_cache": {"<hash>": {"text": "...", "count": N, "first_ch": N}},
        "source_cache": {"<source_hash>": {"title": "...", "blocks": [...]}},
        "blocks": [...]
    }

    Thread-safe: uses threading.Lock per slug for concurrent writes.
    """
    
    # Per-slug locks for thread-safe saves
    _locks: dict[str, threading.Lock] = {}
    
    def __init__(self, slug: str = "global-descent"):
        self.slug = slug
        self._tm_dir = Path(__file__).parent.parent / TM_DIR_NAME
        self._tm_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._tm_dir / f"{slug}.json"
        self._exact_cache: dict[str, dict[str, Any]] = {}
        self._source_cache: dict[str, dict[str, Any]] = {}
        self._blocks: list[dict[str, Any]] = []
        self._loaded = False
        self._dirty = False
        # Thread lock per slug
        if slug not in self._locks:
            self._locks[slug] = threading.Lock()
    
    # ── Path ──────────────────────────────────────────────────────
    
    @staticmethod
    def get_path(slug: str = "global-descent") -> Path:
        return Path(__file__).parent.parent / TM_DIR_NAME / f"{slug}.json"
    
    # ── Load / Save ────────────────────────────────────────────────
    
    def load(self) -> None:
        """Load TM from disk."""
        if self._loaded:
            return
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._exact_cache = data.get("exact_cache", {})
                self._source_cache = data.get("source_cache", {})
                self._blocks = data.get("blocks", [])
            except (json.JSONDecodeError, KeyError):
                self._exact_cache = {}
                self._source_cache = {}
                self._blocks = []
        else:
            self._exact_cache = {}
            self._source_cache = {}
            self._blocks = []
        self._loaded = True
    
    def save(self) -> None:
        """Save TM to disk if dirty. Thread-safe via per-slug lock."""
        if not self._dirty:
            return
        lock = self._locks[self.slug]
        with lock:
            data = {
                "meta": {
                    "version": 2,
                    "slug": self.slug,
                    "blocks": len(self._blocks),
                    "cache_entries": len(self._exact_cache),
                    "source_entries": len(self._source_cache),
                },
                "exact_cache": self._exact_cache,
                "source_cache": self._source_cache,
                "blocks": self._blocks,
            }
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._dirty = False
    
    def force_save(self) -> None:
        """Save regardless of dirty flag."""
        self._dirty = True
        self.save()
    
    # ── Build TM from existing chapters ───────────────────────────
    
    def build_from_chapters(self, chapters_dir: str | Path, chunk_size: int = 50) -> dict:
        """Scan existing translated chapters and populate TM.
        
        Args:
            chapters_dir: Path to chapters/ directory
            chunk_size: Print progress every N chapters
            
        Returns:
            dict with scan stats
        """
        ch_dir = Path(chapters_dir)
        json_files = sorted(ch_dir.glob("*.json"))
        
        added = 0
        skipped = 0
        
        for i, f in enumerate(json_files):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                blocks = data.get("blocks", [])
                ch_num = data.get("num", 0)
                
                for block in blocks:
                    text = block.get("text", "")
                    btype = block.get("type", "?")
                    
                    if not text or btype == "end":
                        continue
                    
                    source = _clean_block(text)
                    if not source or len(source) > MAX_BLOCK_LEN:
                        continue
                    
                    h = _block_hash(source)
                    if h not in self._exact_cache:
                        self._exact_cache[h] = {
                            "text": source,
                            "count": 1,
                            "first_ch": ch_num,
                        }
                        self._blocks.append({
                            "hash": h,
                            "source": source,
                            "type": btype,
                            "ch": ch_num,
                        })
                        added += 1
                    else:
                        self._exact_cache[h]["count"] += 1
                        skipped += 1
                
                if (i + 1) % chunk_size == 0:
                    print(f"  Scanned {i + 1}/{len(json_files)} chs ({added} blocks)")
                    
            except Exception as e:
                print(f"  ⚠ Skipping {f.name}: {e}")
                continue
        
        self._dirty = True
        self.save()
        
        return {
            "chapters_scanned": len(json_files),
            "blocks_added": added,
            "blocks_skipped": skipped,
            "total_blocks": len(self._blocks),
            "cache_entries": len(self._exact_cache),
        }
    
    # ── Lookup ────────────────────────────────────────────────────
    
    def lookup(self, block_text: str) -> tuple[bool, str | None, str]:
        """Look up a block in TM.
        
        Returns:
            (found, translation, method)
            - found=True, translation, "exact" | "fuzzy"
            - found=False, None, "miss"
        """
        self.load()
        
        source = _clean_block(block_text)
        if not source:
            return False, None, "miss"
        
        # L1: Exact match (hash)
        h = _block_hash(source)
        if h in self._exact_cache:
            return True, source, "exact"
        
        # L2: Fuzzy match (Jaccard similarity scan)
        # Only scan last N blocks (most recent are most relevant)
        candidates = self._blocks[-MAX_FUZZY_CANDIDATES:]
        best_score = 0.0
        best_candidate = None
        
        for cand in candidates:
            if not length_ratio_ok(source, cand["source"]):
                continue
            score = jaccard_similarity(source, cand["source"])
            if score > best_score:
                best_score = score
                best_candidate = cand
        
        if best_score >= JACCARD_THRESHOLD and best_candidate:
            return True, best_candidate["source"], "fuzzy"
        
        return False, None, "miss"
    
    # ── Add to TM ─────────────────────────────────────────────────
    
    def add(self, block_text: str, block_type: str = "narration", ch_num: int = 0) -> bool:
        """Add a block to TM if not already present.
        
        Returns True if added, False if already exists.
        End marker blocks are skipped.
        """
        self.load()
        
        if block_type == "end":
            return False
        
        source = _clean_block(block_text)
        if not source or len(source) > MAX_BLOCK_LEN:
            return False
        
        h = _block_hash(source)
        if h in self._exact_cache:
            self._exact_cache[h]["count"] += 1
            return False
        
        self._exact_cache[h] = {
            "text": source,
            "count": 1,
            "first_ch": ch_num,
        }
        self._blocks.append({
            "hash": h,
            "source": source,
            "type": block_type,
            "ch": ch_num,
        })
        self._dirty = True
        return True
    
    def add_batch(self, blocks: list[dict[str, Any]], ch_num: int = 0) -> int:
        """Add multiple blocks to TM.
        
        Returns count of new blocks added.
        """
        added = 0
        for block in blocks:
            text = block.get("text", "")
            btype = block.get("type", "?")
            if btype == "end":
                continue
            if self.add(text, btype, ch_num):
                added += 1
        if added > 0:
            self.save()
        return added

    # ── Source→Translation cache (skip LLM) ───────────────────────

    def _source_hash_key(self, source_text: str) -> str:
        """SHA-256 hash of source text for full-chapter caching."""
        return hashlib.sha256(source_text.encode("utf-8")).hexdigest()[:16]

    def get_source_translation(self, source_text: str) -> dict[str, Any] | None:
        """Look up cached chapter translation by source text hash.
        
        Returns chapter dict (num, title, blocks) if cached, else None.
        """
        self.load()
        key = self._source_hash_key(source_text)
        return self._source_cache.get(key)

    def put_source_translation(self, source_text: str, chapter_data: dict[str, Any]) -> None:
        """Cache a chapter translation by source text hash."""
        self.load()
        key = self._source_hash_key(source_text)
        # Store minimal chapter data (blocks + title + num)
        cached = {
            "num": chapter_data.get("num"),
            "title": chapter_data.get("title"),
            "blocks": chapter_data.get("blocks", []),
            "source": chapter_data.get("source"),
            "lang": chapter_data.get("lang"),
            "output_lang": chapter_data.get("output_lang"),
        }
        self._source_cache[key] = cached
        self._dirty = True
        self.save()
    
    # ── Statistics ─────────────────────────────────────────────────
    
    def stats(self) -> dict[str, Any]:
        """Return statistics about the TM."""
        self.load()
        
        if not self._blocks:
            return {"blocks": 0, "cache_entries": 0, "status": "empty"}
        
        # Count by type
        type_counts: dict[str, int] = {}
        for b in self._blocks:
            bt = b.get("type", "?")
            type_counts[bt] = type_counts.get(bt, 0) + 1
        
        # Duplicate analysis
        high_count = sum(1 for v in self._exact_cache.values() if v["count"] > 1)
        
        return {
            "blocks": len(self._blocks),
            "cache_entries": len(self._exact_cache),
            "by_type": type_counts,
            "high_count_entries": high_count,
            "avg_count": sum(v["count"] for v in self._exact_cache.values()) / max(1, len(self._exact_cache)),
        }
    
    def clear(self) -> None:
        """Clear TM data."""
        self._exact_cache = {}
        self._blocks = []
        self._dirty = True
        self.save()


# ── Standalone CLI ────────────────────────────────────────────────────

def main() -> None:
    import argparse
    
    ap = argparse.ArgumentParser(
        description="Translation Memory management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  novelclaw-tm build              # Build TM from existing chapters
  novelclaw-tm stats              # Show TM statistics
  novelclaw-tm lookup "ข้อความ"   # Look up a block
  novelclaw-tm clear              # Clear TM
""",
    )
    ap.add_argument("--novel", default="global-descent", help="Novel slug")
    ap.add_argument("--chapters-dir", default="", help="Custom chapters directory")
    
    sub = ap.add_subparsers(dest="command")
    sub.add_parser("build", help="Build TM from existing chapters")
    sub.add_parser("stats", help="Show TM statistics")
    sub.add_parser("clear", help="Clear TM")
    look = sub.add_parser("lookup", help="Look up a block in TM")
    look.add_argument("text", nargs="?", help="Block text to look up")
    
    args = ap.parse_args()
    
    if not args.command:
        ap.print_help()
        return
    
    tm = TranslationMemory(args.novel)
    
    if args.command == "build":
        from constants import get_chapters_dir
        ch_dir = args.chapters_dir or str(get_chapters_dir(args.novel))
        print(f"Building TM from {ch_dir}...")
        result = tm.build_from_chapters(ch_dir)
        print(f"✅ Built: {result['blocks_added']} blocks added, "
              f"{result['total_blocks']} total, "
              f"{result['chapters_scanned']} chapters scanned")
    
    elif args.command == "stats":
        s = tm.stats()
        print(f"Translation Memory: {args.novel}")
        print(f"  Blocks:       {s['blocks']}")
        print(f"  Cache entries: {s['cache_entries']}")
        print(f"  Avg count:     {s['avg_count']:.1f}")
        print(f"  High-count:    {s['high_count_entries']}")
        if s.get("by_type"):
            print("  By type:")
            for bt, count in sorted(s["by_type"].items(), key=lambda x: -x[1]):
                print(f"    {bt}: {count}")
    
    elif args.command == "clear":
        tm.clear()
        print(f"✅ TM cleared for {args.novel}")
    
    elif args.command == "lookup":
        if not args.text:
            print("Error: provide text to look up")
            return
        found, translation, method = tm.lookup(args.text)
        if found:
            print(f"✅ Found ({method}): {translation[:100]}")
        else:
            print("❌ Not found in TM")


if __name__ == "__main__":
    main()
