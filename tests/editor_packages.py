#!/usr/bin/env python3
"""Validate the installable artifacts, not just their source manifests."""
import argparse
import json
import re
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(artifacts: Path, version: str) -> None:
    with zipfile.ZipFile(artifacts / f"freak-vscode-{version}.vsix") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("extension/package.json"))
        assert manifest["version"] == version
        xml = ET.fromstring(archive.read("extension.vsixmanifest"))
        identity = xml.find("{*}Metadata/{*}Identity")
        assert identity is not None and identity.attrib["Version"] == version
        assert identity.attrib["Publisher"] == manifest["publisher"]
        for item in manifest["contributes"]["languages"]:
            assert ".fk" in item["extensions"]
            for filename in [item["configuration"], *item["icon"].values()]:
                assert "extension/" + filename.removeprefix("./") in names
        declared = {item["command"] for item in manifest["contributes"]["commands"]}
        client = archive.read("extension/extension.js").decode()
        for menu in manifest["contributes"]["menus"].values():
            assert {item["command"] for item in menu} <= declared
        for command in declared:
            assert f"'{command}'" in client, command
        for kind in ("grammars", "snippets"):
            for item in manifest["contributes"][kind]:
                assert "extension/" + item["path"].removeprefix("./") in names
        snippets = json.loads(archive.read("extension/snippets/freak.json"))
        assert "extension/LICENSE.txt" in names
        for filename in ("extension.js", "freak_lsp.py", "requirements.txt",
                         "node_modules/vscode-languageclient/lib/node/main.js",
                         "node_modules/vscode-jsonrpc/lib/node/main.js"):
            assert "extension/" + filename in names, filename
        assert archive.read("extension/freak_lsp.py") == (ROOT / "lsp/freak_lsp.py").read_bytes()
        assert archive.read("extension/requirements.txt") == (ROOT / "lsp/requirements.txt").read_bytes()

    with zipfile.ZipFile(artifacts / f"freak-zed-{version}.zip") as archive:
        manifest = tomllib.loads(archive.read("freak-zed/extension.toml").decode())
        assert manifest["id"] == "freak-lang" and manifest["schema_version"] == 1
        assert manifest["version"] == version
        grammar = manifest["grammars"]["freak"]
        source_manifest = tomllib.loads((ROOT / "zed/freak-lang/extension.toml").read_text())
        assert grammar == source_manifest["grammars"]["freak"]
        assert re.fullmatch(r"[0-9a-f]{40}", grammar["rev"])
        assert grammar["repository"] == "https://github.com/FREAK-lang-dev/tree-sitter-freak"
        language = tomllib.loads(archive.read("freak-zed/languages/freak/config.toml").decode())
        assert language["grammar"] == "freak" and "fk" in language["path_suffixes"]
        assert manifest["snippets"] == ["snippets/freak.json"]
        assert snippets == json.loads(archive.read("freak-zed/snippets/freak.json"))
        for name in ("highlights", "outline", "brackets", "indents"):
            assert archive.read(f"freak-zed/languages/freak/{name}.scm")
        assert archive.read("freak-zed/LICENSE")
        assert manifest["language_servers"]["freak-lsp"]["languages"] == ["FREAK"]
        assert b"zed_extension_api" in archive.read("freak-zed/Cargo.toml")
        assert b'worktree.which("freak-lsp")' in archive.read("freak-zed/src/lib.rs")

    with zipfile.ZipFile(artifacts / f"freak-litexl-{version}.zip") as archive:
        names = set(archive.namelist())
        assert names == {f"language_freak/{name}" for name in (
            "init.lua", "freak_lsp.py", "requirements.txt", "README.md", "LICENSE")}, names
        plugin = archive.read("language_freak/init.lua").decode()
        assert plugin.startswith("-- mod-version:3")
        assert 'files = { "%.fk$" }' in plugin and '"freak_lsp.py"' in plugin
        assert archive.read("language_freak/freak_lsp.py") == (ROOT / "lsp/freak_lsp.py").read_bytes()
        assert archive.read("language_freak/requirements.txt") == (ROOT / "lsp/requirements.txt").read_bytes()

    sums = (artifacts / "SHA256SUMS").read_text(encoding="utf-8").split()[1::2]
    assert sums == [f"freak-vscode-{version}.vsix", f"freak-zed-{version}.zip",
                    f"freak-litexl-{version}.zip"], sums

    for editor in ("vscode", "zed"):
        source = ROOT / f"{editor}/freak-lang/snippets/freak.json"
        assert snippets == json.loads(source.read_text(encoding="utf-8"))
    assert len(snippets) >= 32, "Preserve the existing editors repository snippets"
    print(f"Editor artifact contracts passed for {version}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--version", default=(ROOT / "VERSION").read_text().strip())
    args = parser.parse_args()
    verify(args.artifacts, args.version)
