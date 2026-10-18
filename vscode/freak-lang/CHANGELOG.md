# Changelog

## [0.15.1] - 2026-10-18

### Added
- Hangar commands for FREAK 0.15.1: install, update, add, outdated, audit,
  registry log in / account / log out, and publish (dry run, or confirmed)
- `freak.build.optimization` and `freak.build.lto` settings for the new
  `--O0`..`--O3`, `--tlto` and `--flto` flags on Run and Build
- `freak.diagnosticCast` setting for `--diagnostic-cast` on Run, Build and Check
- `freak.lsp.command` to launch a different stdio language server in place of
  the bundled Python one

### Fixed
- `pilot mut x = ...` bindings now show up in completion and go to definition
- Files whose names contain `%` escapes are checked as the right file
- Compiler diagnostics appear for files with CRLF line endings
- Rapid saves stop the superseded `freak check` instead of stacking processes

## [0.15.0] - 2026-10-13

### Added
- FREAK 0.15.0 syntax: `while`, `repeat while`, `repeat N times with i`, ranges
  (`..`, `..=`, `step`), C-style `for`, `grounded pilot`, `;` separators,
  capitalised truth literals, and the `\{`, `\}` and `\xHH` escapes
- Compiler diagnostics from `freak check` on open and save
- Run, Check, Build and Test commands with a Problems-panel matcher
- Status bar item showing the installed compiler version
- Go to definition within a file
- Eight snippets for the new loops, `grounded pilot` and `fs::read_checked`

### Changed
- Any `@annotation` is highlighted, not only a fixed list
- Declared task, shape and pilot names receive their own scopes
- `freak.lsp.pythonPath` is auto-detected when empty

### Fixed
- The `when` snippet used `=>`; arms use `->`
- `repeat until` was highlighted only as `repeat`

## [0.1.0] - 2026-03-26

### Added
- TextMate grammar for full FREAK syntax highlighting
- 25+ code snippets for common patterns
- Language configuration (brackets, comments, folding)
- String interpolation highlighting
- Annotation highlighting (@protagonist, @nakige, etc.)
- Namespace/module syntax highlighting (std::fs::read)
