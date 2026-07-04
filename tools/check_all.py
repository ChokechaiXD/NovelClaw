from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def tool(name: str) -> str:
    return shutil.which(name) or shutil.which(f"{name}.cmd") or name


def run(label: str, cmd: list[str]) -> None:
    print(f"[check] {label}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def python_files() -> list[str]:
    files = [ROOT / "novelclaw.py"]
    files.extend(
        path for path in (ROOT / "tools").rglob("*.py")
        if "__pycache__" not in path.parts
    )
    return [str(path.relative_to(ROOT)) for path in files]


def reader_node_test_files() -> list[str]:
    return [
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "reader" / "tests").glob("*.test.js"))
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run NovelClaw quality checks")
    parser.add_argument("--full", action="store_true", help="Run the full Python test suite")
    args = parser.parse_args(argv)

    run("python syntax", [sys.executable, "-m", "py_compile", *python_files()])
    run("reader static/js checks", [tool("npm"), "--prefix", "reader", "run", "check"])
    run(
        "reader node tests",
        [tool("node"), "--test", *reader_node_test_files()],
    )

    if args.full:
        run("python tests", [sys.executable, "-m", "pytest", "tests", "-q"])
    else:
        run(
            "python focused tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_atomic_io.py",
                "tests/test_pipeline_retry.py",
                "tests/test_pipeline_llm_config.py",
                "tests/test_llm_rate_limit.py",
                "tests/test_novelclaw_cli.py",
                "tests/test_provider_config.py",
                "tests/test_glossary_discovery.py",
                "tests/test_import_sources.py",
                "-q",
            ],
        )

    print("[check] all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
