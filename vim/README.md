# FREAK for Vim and Neovim

Syntax highlighting, indentation and `--` comments for `.fk` files in Vim 8.2+
and Neovim 0.9+. Neovim can also use the tree-sitter-freak parser for
highlighting and folds, and start the FREAK language server.

The same directory serves both editors:

| File | Vim | Neovim |
|---|---|---|
| `ftdetect/freak.vim` | `.fk` is filetype `freak` | same |
| `syntax/freak.vim` | Highlighting | Fallback until the parser is installed |
| `indent/freak.vim` | Brace-based indentation (`{`/`}`, `done`) | same |
| `ftplugin/freak.vim` | `commentstring`, four-space indentation | same |
| `queries/freak/*.scm` | | Tree-sitter highlights and folds |
| `lua/freak/init.lua`, `plugin/freak.lua` | | Parser registration and `freak-lsp` |

## Install

**From a release.** Download `freak-vim-<version>.zip` from a
[freak-editors release](https://github.com/FREAK-lang-dev/freak-editors/releases)
and extract it into a package directory, so that `.../start/freak-vim/syntax/freak.vim`
exists:

| Editor | Linux and macOS | Windows |
|---|---|---|
| Vim | `~/.vim/pack/freak/start/` | `%USERPROFILE%\vimfiles\pack\freak\start\` |
| Neovim | `~/.local/share/nvim/site/pack/freak/start/` | `%LOCALAPPDATA%\nvim-data\site\pack\freak\start\` |

Vim needs `filetype plugin indent on` and `syntax on` in its vimrc (Neovim
turns both on by default).

**From Git with a plugin manager.** The runtime files live in the `vim/`
subdirectory of this repository.

vim-plug:

```vim
Plug 'FREAK-lang-dev/freak-editors', { 'rtp': 'vim' }
```

lazy.nvim:

```lua
{
  "FREAK-lang-dev/freak-editors",
  config = function(plugin)
    vim.opt.rtp:append(plugin.dir .. "/vim")
    require("freak").setup()
  end,
}
```

## Neovim: tree-sitter

With [nvim-treesitter](https://github.com/nvim-treesitter/nvim-treesitter)
installed (either its `master` or `main` branch), the plugin registers the
parser, so install it once:

```vim
:TSInstall freak
```

The parser is built from the tree-sitter-freak revision pinned in
`lua/freak/init.lua`, the same one the Zed extension uses. The next `.fk`
buffer you open uses tree-sitter highlighting; until then the regex syntax
stays on. Tree-sitter folds work with:

```lua
vim.opt.foldmethod = "expr"
vim.opt.foldexpr = "v:lua.vim.treesitter.foldexpr()" -- Neovim 0.10+
```

Without nvim-treesitter, build the parser yourself and put it on the
runtimepath as `parser/freak.so` (`freak.dll` on Windows):

```sh
git clone https://github.com/FREAK-lang-dev/tree-sitter-freak
cd tree-sitter-freak
mkdir -p ~/.local/share/nvim/site/parser
cc -O2 -shared -fPIC -Isrc src/parser.c -o ~/.local/share/nvim/site/parser/freak.so
```

## Neovim: language server

When `freak-lsp` (the native FREAK language server, built in Freak-lang with
`python src/compiler/v4/build_lsp.py`) is on your `PATH`, `.fk` buffers start
it automatically, rooted at the nearest `hangar.toml` or `.git`. It gives
hover, go to definition, document symbols, completion and `freak check`
diagnostics.

The release zip also carries the lightweight Python server under `lsp/`. To use
it instead, install its dependencies and point the plugin at it:

```sh
python3 -m pip install -r ~/.local/share/nvim/site/pack/freak/start/freak-vim/lsp/requirements.txt
```

```lua
require("freak").setup({
  lsp_cmd = { "python3", vim.fn.expand("~/.local/share/nvim/site/pack/freak/start/freak-vim/lsp/freak_lsp.py"), "--stdio" },
  lsp_init_options = { compilerPath = "freak" },
})
```

All options and their defaults:

```lua
require("freak").setup({
  treesitter = true,  -- register the parser and use tree-sitter highlighting when installed
  lsp = true,         -- start a language server for .fk buffers
  lsp_cmd = nil,      -- nil finds freak-lsp on PATH
  lsp_init_options = nil,
  root_markers = { "hangar.toml", ".git" },
})
```

`plugin/freak.lua` calls `setup()` with these defaults unless your config
already called it. A later `setup()` call replaces the options; language servers
that are already running keep their old command until you restart them
(`:LspRestart`, or reopen Neovim). Set `vim.g.freak_no_setup = true` before
plugins load to skip the automatic call, for example when you configure
`freak-lsp` through nvim-lspconfig yourself.

## Vim: language server

Vim has no built-in LSP client. With [vim-lsp](https://github.com/prabirshrestha/vim-lsp):

```vim
if executable('freak-lsp')
  autocmd User lsp_setup call lsp#register_server({
        \ 'name': 'freak-lsp',
        \ 'cmd': ['freak-lsp'],
        \ 'allowlist': ['freak'],
        \ })
endif
```

## Options

Set `g:freak_recommended_style = 0` to keep your own `expandtab`,
`shiftwidth`, `softtabstop` and `tabstop` instead of four spaces.

Grammar coverage does not imply that every highlighted form is implemented in
the shipping compiler.
