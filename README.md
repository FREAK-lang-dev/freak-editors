# FREAK editors

Editor integrations and release packaging for the [FREAK language](https://github.com/FREAK-lang-dev/Freak-lang).
This repository owns the VS Code, Zed and Lite XL plugins, their snippets and
queries, the lightweight Python LSP, and the tooling that produces release
downloads. The current release tracks FREAK 0.15.1.

| Download | Install | Included support |
|---|---|---|
| `freak-vscode-<version>.vsix` | VS Code: **Extensions: Install from VSIX...** | Highlighting, snippets, brackets, file icon, Run/Check/Build/Test and Hangar commands, bundled Python LSP client/server |
| `freak-zed-<version>.zip` | Extract, then Zed: **Install Dev Extension** on `freak-zed` | Highlighting, the same snippets, brackets, indentation, outline |
| `freak-litexl-<version>.zip` | Extract into Lite XL's `plugins` directory | Highlighting, comment toggling, bundled Python LSP server for the `lsp` plugin |

See the [VS Code](vscode/freak-lang/README.md), [Zed](zed/freak-lang/README.md)
and [Lite XL](litexl/README.md) installation guides. Packages include licenses
and ship with `SHA256SUMS`. VS Code-compatible editors that support VSIX
installation may use that asset; no marketplace publications are added here.

The Python LSP provides lightweight text-based completion, hover, go to
definition within a file, and basic diagnostics. When a `freak` 0.15.0 or later
compiler is installed it also runs `freak check` on open and save and reports
the compiler's errors until the next edit; without one those diagnostics are
simply absent. It adds
no type or borrow analysis of its own. VS Code (`freak.lsp.command`) and Lite XL
(`server_command`) can launch a different stdio language server instead of the
bundled one. Zed currently ships snippets and grammar
support only. Grammar coverage does not
imply that every highlighted form is implemented in the shipping compiler.

## Build and verify

Use Node.js 22+, Python 3.11+, Git, and a C compiler for Tree-sitter checks.
From this repository's root:

```sh
npm ci
python -m pip install -r lsp/requirements.txt
npm test
python -u tests/editor_grammars.py --remote
python -u tools/package_editors.py --output dist/editors
python -u tests/editor_packages.py --artifacts dist/editors
python -u tests/lsp_stdio.py dist/editors/freak-vscode-0.15.1.vsix
```

Prefer a Python virtual environment. The packager installs locked VS Code runtime
dependencies in a temporary staging directory; it does not use the checked-in
`node_modules`. The canonical bundled server is `lsp/freak_lsp.py`. The compatibility
copies under `vscode/freak-lang` remain for direct extension development.

## Release ownership

`VERSION` controls standalone editor releases. When a push to `main` carries a
`VERSION` that has no `v<version>` tag yet, the release workflow builds, tests,
checksums, and publishes all three downloads and creates the tag at that commit;
merging a pull request that bumps `VERSION` is therefore what releases. Pushing
a matching `v<version>` tag by hand does the same for the tagged commit. A
version that already has a release is never rebuilt. No tag or release is
created by building locally.

FREAK language releases call `.github/workflows/editor-packages.yml` at a pinned
commit, supplying `version` (the compiler release version) and `revision` (the same
immutable freak-editors commit). The reusable workflow explicitly checks out this
repository, even when called from the language repository. It uploads the
`editor-packages` artifact to the caller's run; the caller attaches it to its own
release and incorporates the files in its checksums.

`tools/package_editors.py --version <major.minor.patch>` stamps only staged
manifests. The Lite XL archive has no manifest and takes the version in its name. Development versions stay unchanged. Zed retains the separately
pinned grammar from `FREAK-lang-dev/tree-sitter-freak`; CI fetches and tests that
exact revision. Updating the integration requires updating both the reusable
workflow ref and `revision` in the language repository after the editor change
has passed review.
