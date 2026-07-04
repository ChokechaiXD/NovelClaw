import json
import os
import subprocess
from pathlib import Path

import pytest

import novel_paths


def _reader_paths(slug: str, num: int) -> dict[str, str]:
    script = f"""
const paths = require('./reader/lib/paths');
const slug = {json.dumps(slug)};
const num = {num};
console.log(JSON.stringify({{
  novelDir: paths.novelDir(slug),
  chapterTh: paths.chapterPath(slug, num, 'th'),
  chapterCn: paths.chapterPath(slug, num, 'cn'),
  sourceMd: paths.sourceMdPath(slug, num),
  novelJson: paths.novelJsonPath(slug),
  chaptersIndex: paths.chaptersIndexPath(slug),
  glossaryJson: paths.glossaryJsonPath(slug)
}}));
"""
    env = os.environ.copy()
    env["NOVELCLAW_ROOT"] = str(novel_paths.NOVELS_DIR)
    proc = subprocess.run(
        ["node", "-e", script],
        cwd=novel_paths.PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_python_and_reader_path_helpers_match_for_chapter_files():
    slug = "global-descent"
    num = 7
    reader = _reader_paths(slug, num)

    assert Path(reader["novelDir"]) == novel_paths.novel_dir(slug)
    assert Path(reader["chapterTh"]) == novel_paths.chapter_path(slug, num, "th")
    assert Path(reader["chapterCn"]) == novel_paths.chapter_path(slug, num, "cn")
    assert Path(reader["sourceMd"]) == novel_paths.source_md_path(slug, num)
    assert Path(reader["novelJson"]) == novel_paths.novel_json_path(slug)
    assert Path(reader["chaptersIndex"]) == novel_paths.chapters_index_path(slug)
    assert Path(reader["glossaryJson"]) == novel_paths.glossary_json_path(slug)


def test_python_path_helpers_reject_path_traversal_slugs():
    with pytest.raises(ValueError):
        novel_paths.chapter_path("../outside", 1, "th")

