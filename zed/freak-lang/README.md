# FREAK for Zed

Syntax highlighting, bracket matching, indentation, outline, comment toggling,
and the same snippet library as the VS Code extension.

## Install

1. Download `freak-zed-<version>.zip` from a
   [freak-editors release](https://github.com/FREAK-lang-dev/freak-editors/releases)
   or a FREAK language release that bundles it.
2. Extract it into a permanent directory.
3. In Zed, choose **Install Dev Extension** and select the extracted `freak-zed`
   directory containing `extension.toml`.

Zed fetches the pinned grammar from `FREAK-lang-dev/tree-sitter-freak` and builds
it. The first installation needs Git, internet access, and Zed's
[grammar build prerequisites](https://zed.dev/docs/extensions/developing-extensions).
Keep the extracted directory while installed. Updates use the same install flow
with the new archive. This is a source extension, not a precompiled Gallery
package; Gallery publication is separate.

The extension includes a small Rust part, so Zed needs Rust installed through
`rustup` to build it during a dev install.

Choose snippets such as `task`, `pilot`, `if`, `times`, `foreach`, `shape`, and
`say` from the completion menu, then Tab between placeholders.

## Language server

When `freak-lsp`, the native FREAK language server, is on PATH, Zed starts it
for `.fk` files: hover, go to definition, outline symbols, completion, and
`freak check` diagnostics on open and save. Build it in a Freak-lang checkout
with `python src/compiler/v4/build_lsp.py`. To use a binary that is not on
PATH, or to pass options, add to Zed's settings:

```json
{
  "lsp": {
    "freak-lsp": {
      "binary": { "path": "/path/to/freak-lsp" },
      "initialization_options": { "compilerPath": "freak", "maverickDiagnostics": false }
    }
  }
}
```

Without `freak-lsp` the extension still provides highlighting and snippets. The grammar covers common FREAK forms
through the 0.15.0 loops (`while`, ranges with `step`, C-style `for`) and `grounded pilot`,
not every V4 feature.

## Develop

Build a local archive with `tools/package_editors.py` and install its extracted
`freak-zed` directory. The raw checkout retains historical grammar build files
under `zed/freak-lang/grammars/freak`; those collide with the Git clone directory
Zed creates during a dev install, so use the staged archive for installation.
Queries live beside `languages/freak/config.toml`. The manifest pins the upstream grammar revision;
`python -u tests/editor_grammars.py --remote` verifies the grammar that Zed actually
downloads. The bundled `grammars/freak` source can also be exercised by omitting
`--remote`, but editing that copy alone does not update the installed grammar.
