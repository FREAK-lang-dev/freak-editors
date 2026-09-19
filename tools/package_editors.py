#!/usr/bin/env python3
"""Build release editor assets without modifying their source manifests.

Requires Node.js and `npm ci`. Standalone versions come from VERSION; callers may supply a compiler release version.
Zed retains its independently pinned tree-sitter-freak revision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def copy_files(source: Path, destination: Path, names: list[str]) -> None:
    for name in names:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)


def package(output: Path, version: str) -> list[Path]:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise SystemExit("Version must be major.minor.patch")
    vsce = ROOT / "node_modules/@vscode/vsce/vsce"
    if not vsce.is_file():
        raise SystemExit("Run npm ci before packaging")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    assets = [output / f"freak-vscode-{version}.vsix",
              output / f"freak-zed-{version}.zip"]
    with tempfile.TemporaryDirectory(prefix="freak-editors-") as temporary:
        stage = Path(temporary)
        vscode = stage / "vscode"
        copy_files(ROOT / "vscode/freak-lang", vscode, [
            "package.json", "package-lock.json", ".vscodeignore", "README.md",
            "extension.js", "language-configuration.json",
            "syntaxes/freak.tmLanguage.json", "icons/freak-file.svg",
            "snippets/freak.json",
        ])
        shutil.copyfile(ROOT / "LICENSE", vscode / "LICENSE")
        shutil.copyfile(ROOT / "lsp/freak_lsp.py", vscode / "freak_lsp.py")
        shutil.copyfile(ROOT / "lsp/requirements.txt", vscode / "requirements.txt")
        manifest = json.loads((vscode / "package.json").read_text(encoding="utf-8"))
        manifest["version"] = version
        (vscode / "package.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        lock_path = vscode / "package-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["version"] = version
        lock["packages"][""]["version"] = version
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if npm is None:
            raise SystemExit("npm is required to install the VS Code runtime dependencies")
        subprocess.run([npm, "ci", "--omit=dev", "--ignore-scripts"], cwd=vscode, check=True)
        subprocess.run([
            "node", str(vsce), "package",
            "--out", str(assets[0]),
        ], cwd=vscode, check=True)

        zed = stage / "freak-zed"
        copy_files(ROOT / "zed/freak-lang", zed, [
            "extension.toml", "README.md", "snippets/freak.json",
            "languages/freak/config.toml", "languages/freak/highlights.scm",
            "languages/freak/brackets.scm", "languages/freak/indents.scm",
            "languages/freak/outline.scm",
        ])
        shutil.copyfile(ROOT / "LICENSE", zed / "LICENSE")
        manifest_path = zed / "extension.toml"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest_text = re.sub(r'^version = ".*"$', f'version = "{version}"', manifest_text, flags=re.M)
        manifest_path.write_text(manifest_text, encoding="utf-8", newline="\n")
        with zipfile.ZipFile(assets[1], "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(zed.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(stage).as_posix())
    checksums = "".join(f"{hashlib.sha256(asset.read_bytes()).hexdigest()}  {asset.name}\n" for asset in assets)
    (output / "SHA256SUMS").write_text(checksums, encoding="utf-8", newline="\n")
    return assets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default=read_version())
    args = parser.parse_args()
    for asset in package(args.output, args.version):
        print(asset)


if __name__ == "__main__":
    main()
