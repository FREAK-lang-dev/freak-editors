# FREAK Language Support for VS Code

Syntax highlighting, snippets, compiler commands, and a language server for the **FREAK** programming language.

FREAK is a compiled, statically-typed, memory-safe systems programming language with syntax and aesthetics inspired by anime and visual novels. Files use the `.fk` extension.

## Install a release

Download `freak-vscode-<version>.vsix` from the
[freak-editors releases](https://github.com/FREAK-lang-dev/freak-editors/releases)
or a FREAK language release that bundles these assets. In VS Code, run
**Extensions: Install from VSIX...**, or use:

```sh
code --install-extension freak-vscode-<version>.vsix
```

Highlighting and snippets work immediately. The lightweight Python LSP adds
keyword/symbol completion, hover, go to definition within a file, and basic text
diagnostics. Install Python 3.11+ and accept the dependency installation prompt,
or install the packaged `requirements.txt` into your chosen Python environment
and set `freak.lsp.pythonPath` to that interpreter. Disable `freak.lsp.enabled`
to use only highlighting and snippets.

## Compiler integration

With `freak` 0.15.0 or later on your `PATH` (or `freak.compilerPath` set):

- **Compiler diagnostics.** Opening or saving a `.fk` file runs `freak check` on
  it and shows the shipping compiler's syntax and type errors in the editor.
  They refresh on save and clear when you edit. Turn this off with
  `freak.diagnostics.compiler`.
- **Run, Check and Build** buttons in the editor title bar, and **FREAK: Test
  Project** in the Command Palette. Each runs as a task, so compiler errors also
  land in the Problems panel.
- A status bar item shows the installed compiler version and opens the command
  list. **FREAK: Restart Language Server** reloads the server.

## Features

- Syntax highlighting for `.fk` files
- 32 code snippets for common patterns, including the 0.15 loops
- Bracket matching and auto-closing
- Comment toggling (`--`)
- String interpolation highlighting (`{expr}` in strings)

## Syntax Highlighting

The grammar highlights common FREAK syntax, including:

- **Keywords**: `pilot`, `grounded pilot`, `task`, `give back`, `shape`, `doctrine`, `impl`, `when`, `while`, `eventually`, etc.
- **Loops**: `for each i in 0..=10 step 2`, `repeat 10 times with i`, `repeat while`, `for (init; condition; update)`
- **Types**: `int`, `word`, `bool`, `maybe<T>`, `result<T,E>`, `List<T>`, etc.
- **Annotations**: `@protagonist`, `@nakige`, `@experiment`, `@season_finale`
- **Booleans**: `true`, `false`, `yes`, `no`, `hai`, `iie`, and their capitalised spellings
- **Escapes**: `\n`, `\{`, `\}`, `\x41`; an unknown escape such as `\q` is marked invalid
- **Operators**: `|>` (pipe), `->` (return type), `?` (error propagation)
- **String interpolation**: `"Hello, {name}!"`
- **Namespace access**: `std::fs::read(path)`

## Snippets

| Prefix | Description |
|--------|-------------|
| `main` | Main entry point with `@protagonist` |
| `task` | Function declaration |
| `shape` | Struct declaration |
| `impl` | Implementation block |
| `pilot` | Mutable variable |
| `fixed` / `grounded` | Immutable variable |
| `if` / `ifelse` | Conditionals |
| `when` | Pattern matching |
| `repeat` | Loop (repeat until) |
| `times` / `timeswith` | Counted loop, optionally with a counter |
| `while` / `repeatwhile` | Loop while a condition holds |
| `forrange` / `forstep` | Range loop, optionally with a stride |
| `for` | C-style loop |
| `readchecked` | `fs::read_checked` with `check result` |
| `training` | Training arc (bounded loop) |
| `foreach` | Iterator loop |
| `say` | Print output |
| `give` | Return value |
| `eventually` | Deferred execution |
| `test` | Test block |
| `use` | Module import |
| `extern` | External function |
| `isekai` | Isolated scope |
| `trust` | Unsafe block |

## Example

```freak
use std::math

@protagonist
task main() -> void {
    pilot name: word = "Takeru"
    pilot power: int = 9001

    say "Welcome, {name}!"
    say "Power level: {power}"

    if power > 9000 {
        say "It's over 9000!"
    }

    for each i in 1..=5 {
        say "Training round {i}..."
    }
}
```

## Links

- [FREAK Language Repository](https://github.com/FREAK-lang-dev/Freak-lang)
- [Language Specification](https://github.com/FREAK-lang-dev/Freak-lang/blob/main/freak-full-bible.md)

---

*"It was always going to end this way."*
