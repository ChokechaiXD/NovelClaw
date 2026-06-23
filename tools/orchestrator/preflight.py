"""Preflight checks — validate source/config/index/API before spending tokens."""

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "tools"))

NOVELS_DIR = _PROJECT_ROOT / "novels"


def _novel_dir(slug: str) -> Path:
    return NOVELS_DIR / slug


def _chapters_dir(slug: str) -> Path:
    return _novel_dir(slug) / "chapters"


def _source_path(slug: str, num: int) -> Path:
    return _chapters_dir(slug) / "source" / f"{num:04d}.md"


def _th_path(slug: str, num: int) -> Path:
    return _chapters_dir(slug) / f"{num:04d}.th.json"


def _cn_path(slug: str, num: int) -> Path:
    return _chapters_dir(slug) / f"{num:04d}.cn.json"


def _glossary_json(slug: str) -> Path:
    return _novel_dir(slug) / "glossary" / "glossary.json"


class PreflightResult:
    """Result of a preflight check."""

    def __init__(self):
        self.checks: list[dict] = []
        self.ok = True

    def add(self, name: str, ok: bool, detail: str = ""):
        self.checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            self.ok = False

    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["ok"])
        lines = [f"Preflight: {passed}/{total} checks passed"]
        for c in self.checks:
            icon = "✅" if c["ok"] else "⚠️"
            lines.append(f"  {icon} {c['name']} {c['detail']}")
        return "\n".join(lines)


def run(slug: str, nums: list[int]) -> PreflightResult:
    """Run preflight checks for a range of chapters."""
    result = PreflightResult()
    nd = _novel_dir(slug)

    # 1. Novel directory
    result.add("novel directory", nd.exists(), str(nd))

    # 2. novel.json
    nj = nd / "novel.json"
    result.add("novel.json", nj.exists(), str(nj))

    # 3. chapters.json
    cj = nd / "chapters.json"
    result.add("chapters.json", cj.exists(), str(cj))

    # 4. Glossary
    gj = _glossary_json(slug)
    if gj.exists():
        try:
            data = json.loads(gj.read_text(encoding="utf-8"))
            terms = len(data.get("terms", []))
            result.add("glossary.json", True, f"{terms} terms")
        except Exception as e:
            result.add("glossary.json", False, f"parse error: {e}")
    else:
        result.add("glossary.json", False, "not found")

    # 5. Source files
    found = 0
    missing = []
    for n in nums:
        sp = _source_path(slug, n)
        if sp.exists():
            found += 1
        else:
            missing.append(str(n))
    if missing:
        result.add(f"source files ({len(nums)})", False,
                    f"{found}/{len(nums)} found, missing: {','.join(missing)}")
    else:
        result.add(f"source files ({len(nums)})", True, f"all {found} present")

    # 6. Existing translations
    existing_th = [n for n in nums if _th_path(slug, n).exists()]
    existing_cn = [n for n in nums if _cn_path(slug, n).exists()]
    if existing_th:
        result.add("existing th.json", True,
                    f"{len(existing_th)} chapters: {','.join(str(n) for n in existing_th)}")
    else:
        result.add("existing th.json", True, "none — clean start")
    if existing_cn:
        result.add("existing cn.json", True, f"{len(existing_cn)} chapters")
    else:
        result.add("existing cn.json", True, "none")

    # 7. Staging writable
    staging = _PROJECT_ROOT / "staging" / slug
    try:
        staging.mkdir(parents=True, exist_ok=True)
        result.add("staging dir", True, str(staging))
    except Exception as e:
        result.add("staging dir", False, str(e))

    return result
