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

Choose snippets such as `task`, `pilot`, `if`, `times`, `foreach`, `shape`, and
`say` from the completion menu, then Tab between placeholders. This Zed extension
does not yet launch the repository's Python LSP. Compiler-backed completion,
diagnostics, and hover are not provided. The grammar covers common FREAK forms,
not every V4 feature.

## Develop

Install `zed/freak-lang` directly from this repository. Queries live beside
`languages/freak/config.toml`. The manifest pins the upstream grammar revision;
`python -u tests/editor_grammars.py --remote` verifies the grammar that Zed actually
downloads. The bundled `grammars/freak` source can also be exercised by omitting
`--remote`, but editing that copy alone does not update the installed grammar.
