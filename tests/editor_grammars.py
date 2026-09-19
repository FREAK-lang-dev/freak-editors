#!/usr/bin/env python3
"""Exercise Zed's actual checked-in parser and queries using Tree-sitter."""
from pathlib import Path
import argparse
import os
import re
import shutil
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = ROOT / "zed/freak-lang/grammars/freak"
LANGUAGE = ROOT / "zed/freak-lang/languages/freak"
SAMPLE = ROOT / "tests/sample.fk"
CLI = ROOT / "node_modules/tree-sitter-cli" / (
    "tree-sitter.exe" if os.name == "nt" else "tree-sitter"
)


def run(*args: str) -> str:
    result = subprocess.run([str(CLI), *args], cwd=GRAMMAR, text=True,
                            capture_output=True, check=True)
    return result.stdout


def main() -> None:
    parsed = run("parse", str(SAMPLE))
    assert "ERROR" not in parsed and "MISSING" not in parsed, parsed
    expected = {
        "highlights": [("keyword", "pilot"), ("function", "greet"),
                       ("type.builtin", "word"), ("number", "42"),
                       ("string", "Hello, "), ("keyword.control", "break"),
                       ("keyword.control", "continue")],
        "outline": [("name", "greet"), ("name", "Point")],
        "brackets": [("open", "{"), ("close", "}")],
        "indents": [("start", "{"), ("end", "}")],
    }
    for name, captures in expected.items():
        result = run("query", str(LANGUAGE / f"{name}.scm"), str(SAMPLE))
        for capture, text in captures:
            assert any(f" - {capture}," in line and f"text: `{text}`" in line
                       for line in result.splitlines()), (name, capture, text, result)
        if name == "indents":
            # Zed discards single-line @indent captures. The captured range
            # must span the body, not just the opening brace.
            ranges = re.findall(r"capture: (?:\d+ - )?indent, start: \((\d+), \d+\), end: \((\d+), \d+\)", result)
            assert len(ranges) >= 4, result
            assert all(int(end) > int(start) for start, end in ranges), result
    print("Zed: sample parses without errors; all four queries compile and capture expected syntax")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true", help="Test the exact grammar Zed downloads")
    if parser.parse_args().remote:
        manifest = tomllib.loads((ROOT / "zed/freak-lang/extension.toml").read_text())
        grammar = manifest["grammars"]["freak"]
        assert re.fullmatch(r"[0-9a-f]{40}", grammar["rev"])
        with tempfile.TemporaryDirectory(prefix="freak-grammar-") as temporary:
            GRAMMAR = Path(temporary)
            for command in (["git", "init", "--quiet"],
                            ["git", "fetch", "--depth=1", grammar["repository"], grammar["rev"]],
                            ["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"]):
                subprocess.run(command, cwd=GRAMMAR, check=True, timeout=120)
            main()
    else:
        # Tree-sitter can write native build outputs beside the grammar.
        # Keep even the local smoke out of the source checkout.
        with tempfile.TemporaryDirectory(prefix="freak-grammar-local-") as temporary:
            source = GRAMMAR
            GRAMMAR = Path(temporary)
            shutil.copytree(source / "src", GRAMMAR / "src")
            for name in ("grammar.js", "tree-sitter.json", "package.json"):
                shutil.copyfile(source / name, GRAMMAR / name)
            main()
