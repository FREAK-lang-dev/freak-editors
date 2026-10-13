# FREAK for Lite XL

Syntax highlighting for `.fk` files, `--` comment toggling, and the bundled
Python language server when the [lsp plugin](https://github.com/lite-xl/lite-xl-lsp)
is installed. Requires Lite XL 2.1 or later.

## Install

1. Download `freak-litexl-<version>.zip` from a
   [freak-editors release](https://github.com/FREAK-lang-dev/freak-editors/releases).
2. Extract it into your Lite XL plugins directory, so that
   `plugins/language_freak/init.lua` exists:
   - Linux and macOS: `~/.config/lite-xl/plugins/`
   - Windows: `%USERPROFILE%\.config\lite-xl\plugins\`
3. Restart Lite XL.

Highlighting works immediately and covers FREAK 0.15.0 syntax, including
`while`, `repeat while`, ranges with `step`, and `grounded pilot`.

## Language server

Completion, hover, go to definition and diagnostics need the `lsp` plugin plus
Python 3.11+ with the server's dependencies:

```sh
python -m pip install -r ~/.config/lite-xl/plugins/language_freak/requirements.txt
```

With `freak` 0.15.0 or later on your `PATH`, opening or saving a file also
reports the compiler's own `freak check` errors; they clear when you edit.

Override the defaults in your user `init.lua` before the plugin loads:

```lua
local config = require "core.config"
config.plugins.language_freak = {
  python = "/path/to/venv/bin/python",
  compiler = "/path/to/freak",
  compiler_diagnostics = true,
  lsp = true,
}
```

The server is the same lightweight text-based one the VS Code extension bundles;
it is not compiler-backed type or borrow analysis beyond what `freak check` reports.
