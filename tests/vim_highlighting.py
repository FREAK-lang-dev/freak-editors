#!/usr/bin/env python3
"""Check the Vim and Neovim runtime files in vim/ inside real editors.

Vim (and Neovim without the parser) must give the regex syntax groups below
and re-indent the fixtures to their canonical indentation. With --treesitter,
Neovim must also load the tree-sitter-freak revision pinned in
vim/lua/freak/init.lua and give the nvim-treesitter captures below.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "vim"
SAMPLE = ROOT / "tests/sample.fk"
EXTENDED = ROOT / "tests/vim/extended.fk"
FIXTURES = [SAMPLE, EXTENDED]

# (fixture, text that starts the search on the first line containing it,
#  token at or after that point, expected value)
SYNTAX = [
    (SAMPLE, "-- Highlighting", "keywords", "freakComment"),
    (SAMPLE, "shape Point", "shape", "freakStructure"),
    (SAMPLE, "shape Point", "Point", "freakTypeDecl"),
    (SAMPLE, "x: num", "num", "freakType"),
    (SAMPLE, "task greet", "task", "freakKeyword"),
    (SAMPLE, "task greet", "greet", "freakFuncName"),
    (SAMPLE, "pilot answer", "pilot", "freakStorage"),
    (SAMPLE, "pilot answer", "42", "freakNumber"),
    (SAMPLE, 'say "Hello', "say", "freakBuiltin"),
    (SAMPLE, 'say "Hello', "Hello", "freakString"),
    (SAMPLE, 'say "Hello', "{", "freakInterpolationDelim"),
    (SAMPLE, "repeat 3 times {", "repeat", "freakRepeat"),
    (SAMPLE, "repeat 3 times {", "times", "freakRepeat"),
    (SAMPLE, "if answer", "if", "freakConditional"),
    (SAMPLE, "if answer", "==", "freakOperator"),
    (SAMPLE, "break", "break", "freakStatement"),
    (SAMPLE, "grounded pilot", "grounded", "freakStorage"),
    (SAMPLE, "for each i", "..=", "freakOperator"),
    (SAMPLE, "for each i", "step", "freakRepeat"),
    (SAMPLE, "pilot ready", "TRUE", "freakBoolean"),
    (SAMPLE, 'say "braces', "\\{", "freakEscape"),
    (SAMPLE, 'greet("Takeru")', "greet", "freakFuncCall"),
    (EXTENDED, "-- TODO", "TODO", "freakTodo"),
    (EXTENDED, "use std::fs", "use", "freakInclude"),
    (EXTENDED, "use std::fs", "std", "freakNamespace"),
    (EXTENDED, "@protagonist", "@protagonist", "freakAnnotation"),
    (EXTENDED, "route Tier", "route", "freakStructure"),
    (EXTENDED, "give back", "give", "freakStatement"),
    (EXTENDED, "give back", "back", "freakStatement"),
    (EXTENDED, "maybe<int>", "maybe", "freakType"),
    (EXTENDED, "pilot mut", "mut", "freakStorage"),
    (EXTENDED, "0xFF", "0xFF", "freakNumber"),
    (EXTENDED, "3.14", "3.14", "freakFloat"),
    (EXTENDED, "when level", "when", "freakConditional"),
    (EXTENDED, "give back nobody", "nobody", "freakConstant"),
    (EXTENDED, "give back some", "some", "freakBuiltin"),
    (EXTENDED, "and not false", "and", "freakOperatorWord"),
    (EXTENDED, "and not false", "false", "freakBoolean"),
    (EXTENDED, "eventually {", "eventually", "freakSpecial"),
]

CAPTURES = [
    (SAMPLE, "-- Highlighting", "keywords", "comment"),
    (SAMPLE, "shape Point", "shape", "keyword.type"),
    (SAMPLE, "shape Point", "Point", "type.definition"),
    (SAMPLE, "x: num", "x", "variable.member"),
    (SAMPLE, "task greet", "task", "keyword.function"),
    (SAMPLE, "task greet", "greet", "function"),
    (SAMPLE, "task greet", "name", "variable.parameter"),
    (SAMPLE, "task greet", "word", "type.builtin"),
    (SAMPLE, "pilot answer", "pilot", "keyword"),
    (SAMPLE, "pilot answer", "42", "number"),
    (SAMPLE, 'say "Hello', "say", "function.builtin"),
    (SAMPLE, 'say "Hello', "Hello", "string"),
    (SAMPLE, 'say "Hello', "{", "punctuation.special"),
    (SAMPLE, "repeat 3 times {", "repeat", "keyword.repeat"),
    (SAMPLE, "if answer", "if", "keyword.conditional"),
    (SAMPLE, "break", "break", "keyword.repeat"),
    (SAMPLE, "grounded pilot", "grounded", "keyword.modifier"),
    (SAMPLE, "for each i", "..=", "operator"),
    (SAMPLE, "for each i", "step", "keyword.repeat"),
    (SAMPLE, "while n < 99", "while", "keyword.repeat"),
    (SAMPLE, "pilot ready", "TRUE", "boolean"),
    (SAMPLE, 'say "braces', "\\{", "string.escape"),
    (SAMPLE, 'greet("Takeru")', "greet", "function.call"),
    (EXTENDED, "use std::fs", "use", "keyword.import"),
    (EXTENDED, "@protagonist", "protagonist", "attribute"),
    (EXTENDED, "route Tier", "Tier", "type.definition"),
    (EXTENDED, "Soldier,", "Soldier", "constant"),
    (EXTENDED, "impl Eishi", "impl", "keyword"),
    (EXTENDED, "give back", "give", "keyword.return"),
    (EXTENDED, "pilot mut", "mut", "keyword.modifier"),
    (EXTENDED, "0xFF", "0xFF", "number"),
    (EXTENDED, "give back nobody", "nobody", "constant.builtin"),
    (EXTENDED, "power_up", "power_up", "function.method.call"),
    (EXTENDED, "fs::read", "fs", "module"),
    (EXTENDED, "fs::read", "read", "function.call"),
    (EXTENDED, "and not false", "and", "keyword.operator"),
    (EXTENDED, "eventually {", "eventually", "keyword"),
]


def position(path: Path, context: str, token: str) -> tuple[int, int]:
    """1-based line and byte column of `token` at or after `context`."""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        start = line.find(context)
        if start >= 0:
            column = line.find(token, start)
            assert column >= 0, (path.name, context, token)
            return number, column + 1
    raise AssertionError(f"{path.name}: no line contains {context!r}")


def vimscript(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_editor(command: list[str], script: Path, output: Path) -> dict:
    env = dict(os.environ, HOME=str(script.parent), XDG_CONFIG_HOME=str(script.parent),
               XDG_DATA_HOME=str(script.parent), XDG_STATE_HOME=str(script.parent))
    result = subprocess.run([*command, "-S", str(script)], text=True, capture_output=True,
                            timeout=120, env=env, stdin=subprocess.DEVNULL)
    if not output.exists():
        raise AssertionError(f"{command[0]} wrote no results\n{result.stdout}\n{result.stderr}")
    return json.loads(output.read_text(encoding="utf-8"))


def regex_checks(editor: str, temporary: Path) -> None:
    """Syntax groups, filetype settings and indentation from the Vim script files."""
    output = temporary / f"{Path(editor).stem}-regex.json"
    script = temporary / f"{Path(editor).stem}-regex.vim"
    lines = [
        "set nocompatible",
        f"let &runtimepath = {json.dumps(str(RUNTIME))} . ',' . &runtimepath",
        "filetype plugin indent on",
        "syntax on",
        "let g:results = {'syntax': [], 'files': {}}",
    ]
    for fixture in FIXTURES:
        lines += [
            f"execute 'edit' fnameescape({json.dumps(str(fixture))})",
            "let g:results.files[expand('%:t')] = {'filetype': &filetype,"
            " 'syntax': get(b:, 'current_syntax', ''), 'commentstring': &commentstring,"
            " 'shiftwidth': &shiftwidth, 'indentexpr': &indentexpr}",
        ]
        for path, context, token, _ in SYNTAX:
            if path == fixture:
                line, column = position(path, context, token)
                lines.append("call add(g:results.syntax, synIDattr("
                             f"synID({line}, {column}, 1), 'name'))")
        lines += [
            "silent %s/^\\s\\+//e",
            "silent normal! gg=G",
            "let g:results.files[expand('%:t')].indented = getline(1, '$')",
            "set nomodified",
        ]
    lines += [f"call writefile([json_encode(g:results)], {json.dumps(str(output))})", "qall!"]
    vimscript(script, lines)
    if Path(editor).stem == "nvim":
        command = [editor, "--headless", "-u", "NONE", "-i", "NONE", "-n",
                   "--cmd", "let g:freak_no_setup = 1"]
    else:
        command = [editor, "-N", "-u", "NONE", "-i", "NONE", "-n", "-es"]
    results = run_editor(command, script, output)

    actual = results["syntax"]
    failures = [f"{path.name}: {token!r} after {context!r} is {got or 'unhighlighted'}, want {want}"
                for (path, context, token, want), got in zip(SYNTAX, actual) if got != want]
    assert len(actual) == len(SYNTAX), actual
    for fixture in FIXTURES:
        info = results["files"][fixture.name]
        assert info["filetype"] == "freak" and info["syntax"] == "freak", info
        assert info["commentstring"] == "-- %s" and info["shiftwidth"] == 4, info
        assert info["indentexpr"].startswith("FreakIndent"), info
        canonical = fixture.read_text(encoding="utf-8").splitlines()
        for number, (want, got) in enumerate(zip(canonical, info["indented"]), 1):
            if want != got:
                failures.append(f"{fixture.name}:{number} re-indents to {got!r}, want {want!r}")
        assert len(canonical) == len(info["indented"]), fixture
    assert not failures, "\n".join(failures)
    print(f"{Path(editor).stem}: {len(SYNTAX)} regex syntax groups and indentation of "
          f"{len(FIXTURES)} fixtures match")


def pinned_revision() -> str:
    lua = (RUNTIME / "lua/freak/init.lua").read_text(encoding="utf-8")
    revision = re.search(r'revision = "([0-9a-f]{40})"', lua).group(1)
    zed = tomllib.loads((ROOT / "zed/freak-lang/extension.toml").read_text(encoding="utf-8"))
    assert revision == zed["grammars"]["freak"]["rev"], "Neovim and Zed pin different grammars"
    return revision


def build_parser(temporary: Path, grammar: Path | None) -> Path:
    if grammar is None:
        grammar = temporary / "tree-sitter-freak"
        grammar.mkdir()
        for command in (["git", "init", "--quiet"],
                        ["git", "fetch", "--quiet", "--depth=1",
                         "https://github.com/FREAK-lang-dev/tree-sitter-freak", pinned_revision()],
                        ["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"]):
            subprocess.run(command, cwd=grammar, check=True, timeout=120)
    compiler = os.environ.get("CC") or shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    assert compiler, "A C compiler is needed to build the parser"
    library = temporary / "freak.so"
    subprocess.run([compiler, "-O1", "-shared", "-fPIC", "-I", str(grammar / "src"),
                    str(grammar / "src/parser.c"), "-o", str(library)], check=True, timeout=300)
    return library


def treesitter_checks(nvim: str, temporary: Path, grammar: Path | None) -> None:
    library = build_parser(temporary, grammar)
    output = temporary / "nvim-ts.json"
    script = temporary / "nvim-ts.lua"
    probes = [{"file": path.name, "line": line - 1, "col": column - 1}
              for path, context, token, _ in CAPTURES
              for line, column in [position(path, context, token)]]
    files = {fixture.name: str(fixture) for fixture in FIXTURES}
    script.write_text(f"""
vim.opt.runtimepath:prepend({json.dumps(str(RUNTIME), ensure_ascii=False)})
vim.cmd("filetype plugin indent on")
vim.cmd("syntax on")
vim.treesitter.language.add("freak", {{ path = {json.dumps(str(library), ensure_ascii=False)} }})
require("freak").setup({{ lsp = false }})
local files = vim.json.decode({json.dumps(json.dumps(files), ensure_ascii=False)})
local probes = vim.json.decode({json.dumps(json.dumps(probes))})
local results = {{ captures = {{}}, highlighting = {{}}, queries = {{}} }}
local buffers = {{}}
for name, path in pairs(files) do
  vim.cmd("edit " .. vim.fn.fnameescape(path))
  local buf = vim.api.nvim_get_current_buf()
  buffers[name] = buf
  results.highlighting[name] = vim.treesitter.highlighter.active[buf] ~= nil
  -- Headless Neovim never redraws, and 0.11 only parses for a redraw.
  vim.treesitter.get_parser(buf, "freak"):parse(true)
end
for _, kind in ipairs({{ "highlights", "folds" }}) do
  local ok, query = pcall(vim.treesitter.query.get, "freak", kind)
  results.queries[kind] = ok and query ~= nil or tostring(query)
end
for _, probe in ipairs(probes) do
  local names = {{}}
  for _, capture in ipairs(vim.treesitter.get_captures_at_pos(buffers[probe.file], probe.line, probe.col)) do
    table.insert(names, capture.capture)
  end
  table.insert(results.captures, names)
end
vim.fn.writefile({{ vim.json.encode(results) }}, {json.dumps(str(output), ensure_ascii=False)})
vim.cmd("qall!")
""", encoding="utf-8")
    results = run_editor([nvim, "--headless", "-u", "NONE", "-i", "NONE", "-n"], script, output)
    assert results["queries"] == {"highlights": True, "folds": True}, results["queries"]
    assert all(results["highlighting"].values()), results["highlighting"]
    failures = []
    for (path, context, token, want), names in zip(CAPTURES, results["captures"]):
        # Neovim applies the last matching pattern, which the query orders
        # from general to specific.
        names = [name for name in names if name not in ("spell", "nospell")]
        got = names[-1] if names else None
        if got != want:
            failures.append(f"{path.name}: {token!r} after {context!r} is {names}, want {want} last")
    assert len(results["captures"]) == len(CAPTURES)
    assert not failures, "\n".join(failures)
    print(f"nvim: tree-sitter highlighting starts; {len(CAPTURES)} captures match")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vim", default=shutil.which("vim"), help="Vim executable")
    parser.add_argument("--nvim", default=shutil.which("nvim"), help="Neovim executable")
    parser.add_argument("--treesitter", action="store_true",
                        help="Also build the pinned parser and check Neovim's tree-sitter captures")
    parser.add_argument("--grammar", type=Path,
                        help="Use this tree-sitter-freak checkout instead of fetching the pinned revision")
    parser.add_argument("--require", action="store_true", help="Fail when Vim or Neovim is missing")
    args = parser.parse_args()
    pinned_revision()
    with tempfile.TemporaryDirectory(prefix="freak-vim-") as name:
        temporary = Path(name)
        for label, editor in (("Vim", args.vim), ("Neovim", args.nvim)):
            if editor:
                regex_checks(editor, temporary)
            elif args.require:
                raise SystemExit(f"{label} not found")
            else:
                print(f"{label} not found; skipped")
        if args.treesitter:
            if not args.nvim:
                raise SystemExit("--treesitter needs Neovim")
            treesitter_checks(args.nvim, temporary, args.grammar)


if __name__ == "__main__":
    main()
