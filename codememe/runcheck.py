"""Run a lesson's code and compare its output - so a meme never teaches code that does not work.

A toolchain that is not installed is a warning, not a failure."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

TIMEOUT = 15


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, check=False)


def _plan(language: str, work: Path, source: str):
    """(compile command or None, run command, toolchain binary)"""
    lang = language.lower()
    if lang == "python":
        (work / "main.py").write_text(source)
        return None, ["python3", "-I", "main.py"], "python3"
    if lang in ("c++", "cpp"):
        (work / "main.cpp").write_text(source)
        return ["g++", "-std=c++20", "-Wall", "-o", "main", "main.cpp"], ["./main"], "g++"
    if lang == "c":
        (work / "main.c").write_text(source)
        return ["gcc", "-Wall", "-o", "main", "main.c"], ["./main"], "gcc"
    if lang == "rust":
        (work / "main.rs").write_text(source)
        return ["rustc", "--edition", "2021", "-o", "main", "main.rs"], ["./main"], "rustc"
    if lang in ("javascript", "js"):
        (work / "main.js").write_text(source)
        return None, ["node", "main.js"], "node"
    if lang == "go":
        (work / "main.go").write_text(source)
        return None, ["go", "run", "main.go"], "go"
    return None, [], ""


def run_snippet(language: str, source: str, expect: str, expected_output: str) -> tuple[str | None, str | None]:
    """(problem, note). expect "ok": must run and print expected_output; "error": must fail, and the
    message must contain expected_output."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        compile_cmd, run_cmd, tool = _plan(language, work, source)
        if not run_cmd:
            return None, f"no runner for {language}; code not executed"
        if not shutil.which(tool):
            return None, f"{tool} is not installed; code not executed"
        try:
            if compile_cmd:
                built = _run(compile_cmd, work)
                if built.returncode != 0:
                    if expect == "error" and expected_output.strip() in built.stderr:
                        return None, None
                    return f"does not compile: {built.stderr.strip()[:200]}", None
            done = _run(run_cmd, work)
        except subprocess.TimeoutExpired:
            return f"runs longer than {TIMEOUT}s", None
        if expect == "error":
            if done.returncode == 0:
                return "was marked expect=error but ran fine", None
            return (None, None) if expected_output.strip() in done.stderr else (
                f"error text does not contain the expected_output; got: {done.stderr.strip()[-150:]}", None)
        if done.returncode != 0:
            return f"crashed: {done.stderr.strip()[-200:]}", None
        got, want = done.stdout.strip(), expected_output.strip()
        if got != want:
            return f"prints {got[:80]!r} but expected_output says {want[:80]!r}", None
    return None, None
