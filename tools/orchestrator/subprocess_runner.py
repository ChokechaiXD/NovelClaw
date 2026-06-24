"""
Subprocess runner — standardized command execution wrapper.

Wraps subprocess calls into a structured CommandResult dataclass with
captured stdout, stderr, latency, exit code, and error details.

Usage:
    from orchestrator.subprocess_runner import run_cmd, CommandResult

    result = run_cmd(["python", "script.py", "--flag"], timeout=120)
    if result.ok:
        print(result.stdout)
    else:
        print(f"Failed: {result.error}")
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence


@dataclasses.dataclass
class CommandResult:
    """Standardized result from running a shell command."""

    ok: bool
    cmd: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    elapsed_ms: int
    error: str | None = None
    timed_out: bool = False

    def __str__(self) -> str:
        status = "✅" if self.ok else "❌"
        cmd_str = " ".join(self.cmd)
        return (
            f"{status} {cmd_str} "
            f"(exit={self.returncode}, {self.elapsed_ms}ms)"
        )


def run_cmd(
    cmd: Sequence[str],
    *,
    timeout: int = 120,
    cwd: str | Path | None = None,
    input_data: str | None = None,
    env: dict[str, str] | None = None,
    capture_stderr: bool = True,
) -> CommandResult:
    """Execute a command and return structured result.

    Args:
        cmd: Command and arguments (list of strings).
        timeout: Max seconds to wait before raising TimeoutError.
        cwd: Working directory (default: current).
        input_data: Optional stdin string.
        env: Optional environment variable overrides.
        capture_stderr: If True, include stderr in result (default).

    Returns:
        CommandResult with captured output and metadata.
    """
    start = time.monotonic()
    cmd_list = list(cmd)
    try:
        proc = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            env=env,
            input=input_data,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        return CommandResult(
            ok=proc.returncode == 0,
            cmd=cmd_list,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "" if capture_stderr else "",
            elapsed_ms=elapsed,
            error=proc.stderr.strip()[:500] if proc.stderr and proc.returncode != 0 else None,
        )
    except subprocess.TimeoutExpired:
        elapsed = int((time.monotonic() - start) * 1000)
        return CommandResult(
            ok=False,
            cmd=cmd_list,
            returncode=None,
            stdout="",
            stderr="",
            elapsed_ms=elapsed,
            error=f"Command timed out after {timeout}s",
            timed_out=True,
        )
    except FileNotFoundError as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return CommandResult(
            ok=False,
            cmd=cmd_list,
            returncode=None,
            stdout="",
            stderr="",
            elapsed_ms=elapsed,
            error=str(e),
        )


def run_python(
    script: Path | str,
    *args: str,
    timeout: int = 120,
    cwd: str | Path | None = None,
    input_data: str | None = None,
) -> CommandResult:
    """Run a Python script with args via sys.executable."""
    cmd = [sys.executable, str(script), *args]
    return run_cmd(cmd, timeout=timeout, cwd=cwd, input_data=input_data)
