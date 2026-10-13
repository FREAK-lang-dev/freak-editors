# Changelog

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
