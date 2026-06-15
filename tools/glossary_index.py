"""glossary_index.py — Inverted index for glossary term lookup.

Instead of loading the full glossary.yml (82KB) for every chapter,
this module builds an inverted index: term -> set of chapter numbers
where the term is likely to appear.

Usage:
    from glossary_index import GlossaryIndex
    idx = GlossaryIndex()
    idx.build()
    relevant_terms = idx.lookup(chapter_num=101)
"""

import re
import yaml
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).parent
_NOVEL_ROOT_DEFAULT = SCRIPT_DIR.parent / "novels" / "global-descent"
GLOSSARY_YML = _NOVEL_ROOT_DEFAULT / "glossary" / "glossary.yml"
CHAPTERS_DIR = _NOVEL_ROOT_DEFAULT / "chapters"
INDEX_FILE = _NOVEL_ROOT_DEFAULT / "glossary" / ".glossary_index.json"


class GlossaryIndex:
    """Inverted index: term -> {chapters} where term likely appears."""

    def __init__(self):
        self.terms = {}          # source -> {thai, category, priority, chapters}
        self.chapter_terms = {}  # chapter_num -> [terms]
        self._loaded = False

    def build(self, force=False):
        """Build index from glossary.yml + chapter files.

        Uses cached index if glossary.yml hasn't changed since last build.
        """
        import json
        import os

        if not force and INDEX_FILE.exists():
            # Check if glossary.yml is newer than index
            yml_mtime = os.path.getmtime(GLOSSARY_YML) if GLOSSARY_YML.exists() else 0
            idx_mtime = os.path.getmtime(INDEX_FILE)
            if idx_mtime >= yml_mtime:
                data = json.loads(INDEX_FILE.read_text(encoding='utf-8'))
                self.terms = data.get('terms', {})
                self.chapter_terms = {int(k): v for k, v in data.get('chapter_terms', {}).items()}
                self._loaded = True
                return

        # Load glossary
        if not GLOSSARY_YML.exists():
            return

        with open(GLOSSARY_YML, encoding='utf-8') as f:
            data = yaml.safe_load(f)

        self.terms = {}
        for entry in data.get('terms', []):
            source = entry.get('source', '')
            if source:
                self.terms[source] = {
                    'thai': entry.get('thai', ''),
                    'category': entry.get('category', ''),
                    'priority': int(entry.get('priority', 3)),
                }

        # Scan all chapters to build inverted index
        self.chapter_terms = defaultdict(list)
        for ch_file in sorted(CHAPTERS_DIR.glob("*.json")):
            if not ch_file.stem.isdigit():
                continue
            ch_num = int(ch_file.stem)
            try:
                import json as j
                content = j.loads(ch_file.read_text(encoding='utf-8'))
                blocks = content.get('blocks', [])
                text = ' '.join(b.get('text', '') for b in blocks)

                # Find which glossary terms appear in this chapter
                found = []
                for source, info in self.terms.items():
                    if source in text or info['thai'] in text:
                        found.append(source)
                        if 'chapters' not in self.terms[source]:
                            self.terms[source]['chapters'] = []
                        self.terms[source]['chapters'].append(ch_num)

                self.chapter_terms[ch_num] = found
            except Exception:
                pass

        # Save index
        INDEX_FILE.write_text(json.dumps({
            'terms': self.terms,
            'chapter_terms': {str(k): v for k, v in self.chapter_terms.items()},
        }, ensure_ascii=False, indent=2), encoding='utf-8')

        self._loaded = True

    def lookup(self, chapter_num=None, text=None):
        """Get relevant terms for a chapter or text.

        Returns list of (source, thai, priority) tuples.
        """
        if not self._loaded:
            self.build()

        found = set()

        # From chapter index
        if chapter_num and chapter_num in self.chapter_terms:
            for source in self.chapter_terms[chapter_num]:
                found.add(source)

        # From text scan
        if text:
            for source, info in self.terms.items():
                if source in text or info.get('thai', '') in text:
                    found.add(source)

        # Always include locked terms (priority 1)
        result = []
        for source in found:
            info = self.terms.get(source, {})
            result.append((source, info.get('thai', ''), info.get('priority', 3)))

        # Sort by priority (1 first)
        result.sort(key=lambda x: x[2])
        return result

    def get_context_block(self, chapter_num=None, text=None):
        """Generate a compact context block for AI prompt.

        Returns markdown string with relevant glossary terms.
        """
        terms = self.lookup(chapter_num=chapter_num, text=text)

        if not terms:
            return ""

        lines = ["## Relevant Glossary Terms", ""]
        current_priority = None

        for source, thai, priority in terms:
            if priority != current_priority:
                if priority == 1:
                    lines.append("### P1 (Locked - Never Deviate)")
                elif priority == 2:
                    lines.append("### P2 (Reference - Use Consistently)")
                else:
                    lines.append("### P3 (Auto - Suggestion)")
                current_priority = priority
            lines.append(f"- {source} → {thai}")

        return "\n".join(lines)


# CLI
if __name__ == '__main__':
    import sys
    idx = GlossaryIndex()

    if '--build' in sys.argv:
        idx.build(force=True)
        print(f"Index built: {len(idx.terms)} terms, {len(idx.chapter_terms)} chapters")

    elif '--lookup' in sys.argv:
        ch_num = int(sys.argv[sys.argv.index('--lookup') + 1])
        terms = idx.lookup(chapter_num=ch_num)
        print(f"Terms for ch {ch_num}: {len(terms)}")
        for src, thai, prio in terms[:20]:
            print(f"  [{prio}] {src} → {thai}")

    elif '--context' in sys.argv:
        ch_num = int(sys.argv[sys.argv.index('--context') + 1])
        block = idx.get_context_block(chapter_num=ch_num)
        print(block)

    else:
        print("Usage: python glossary_index.py [--build | --lookup N | --context N]")
