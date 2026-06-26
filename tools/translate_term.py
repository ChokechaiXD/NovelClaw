"""
tools/translate_term.py — Translate individual Chinese novel terms to Thai in context.
Outputs structured JSON results.
"""

import sys
import json
import re
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from llm_router.router import call_profile


def main():
    # Reconfigure streams to UTF-8 on Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")

    try:
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print(json.dumps({"error": "Empty input"}), file=sys.stderr)
            sys.exit(1)

        input_data = json.loads(raw_input)
        term = input_data.get("term", "").strip()
        context = input_data.get("context", "").strip()

        if not term:
            print(json.dumps({"error": "Missing term"}), file=sys.stderr)
            sys.exit(1)

        # Build prompt
        prompt = f"""You are an expert Chinese-to-Thai translator for web novels.
Translate the following Chinese term to Thai in the context of this web novel.

Term: {term}
Context: {context}

Respond ONLY with a JSON object in this format (no other text, no markdown fences):
{{
  "thai": "Thai translation",
  "category": "ตัวละคร" or "สถานที่" or "สกิล" or "ไอเทม" or "คำศัพท์",
  "explanation": "Brief explanation in Thai"
}}"""

        # Call LLM router with fast profile
        result = call_profile("fast", prompt)
        if not result.ok:
            # Fallback retry with translate_fast
            result = call_profile("translate_fast", prompt)

        if result.ok:
            text = result.text.strip()
            # Strip markdown code fences if LLM added them anyway
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*\n?", "", text)
                text = re.sub(r"\n?```\s*$", "", text)
            
            # Parse and validate JSON structure
            parsed = json.loads(text.strip())
            
            # Normalise categories
            category = parsed.get("category", "คำศัพท์")
            if category not in ("ตัวละคร", "สถานที่", "สกิล", "ไอเทม", "คำศัพท์"):
                parsed["category"] = "คำศัพท์"
                
            print(json.dumps(parsed, ensure_ascii=False))
        else:
            print(json.dumps({"error": f"LLM error: {result.error}"}), file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Exception: {str(e)}"}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
