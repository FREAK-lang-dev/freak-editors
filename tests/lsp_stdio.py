"""Initialize the packaged Python server and exercise it over stdio."""
import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path

SOURCE = """task greet(name: word) -> void {
    fixed pilot x = 1
    x = 2
}
wh
greet("Takeru")
say gr
"""

# What `freak check` 0.15.0 prints for SOURCE's reassignment, colours included.
COMPILER_OUTPUT = """Source length: 86
  \x1b[1;32mOK\x1b[0m  Parsing\x1b[2m (13ms)\x1b[0m
\x1b[1;31mtype error\x1b[0m: fixed pilot cannot be modified (line 3)
 --> sample.fk:3:1
3 |     x = 2
  | ^
  \x1b[1;31mX FAILED\x1b[0m\x1b[2m -- type/borrow errors found\x1b[0m
"""


def fake_compiler(directory: Path) -> Path:
    """A stand-in `freak` that answers `check` with COMPILER_OUTPUT."""
    script = directory / "fake_freak.py"
    script.write_text(
        "import sys\n"
        "assert sys.argv[1:] == ['check', 'sample.fk'], sys.argv\n"
        f"sys.stdout.buffer.write({COMPILER_OUTPUT.encode()!r})\n"
        "sys.exit(1)\n", encoding="utf-8")
    if os.name == "nt":
        launcher = directory / "fake_freak.cmd"
        launcher.write_text(f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8")
    else:
        launcher = directory / "fake_freak"
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return launcher


def verify(vsix: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="freak-lsp-test-") as temporary:
        with zipfile.ZipFile(vsix) as archive:
            script = Path(temporary) / "freak_lsp.py"
            script.write_bytes(archive.read("extension/freak_lsp.py"))
        compiler = fake_compiler(Path(temporary))
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([sys.executable, "-u", str(script), "--stdio"],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
            messages = queue.Queue()
            notifications = []

            def reader():
                while True:
                    headers = {}
                    while line := process.stdout.readline():
                        if line == b"\r\n":
                            break
                        key, value = line.decode().split(":", 1)
                        headers[key.lower()] = value.strip()
                    if not line:
                        return
                    data = process.stdout.read(int(headers["content-length"]))
                    messages.put(json.loads(data))

            thread = threading.Thread(target=reader, daemon=True)
            thread.start()

            def send(message):
                payload = json.dumps({"jsonrpc": "2.0", **message}).encode()
                process.stdin.write(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
                process.stdin.flush()

            def response(identifier):
                # Bound notifications as well as elapsed wait time.
                for _ in range(20):
                    result = messages.get(timeout=15)
                    if result.get("id") == identifier:
                        assert "error" not in result, result
                        return result["result"]
                    notifications.append(result)
                raise AssertionError("Too many notifications without a response")

            def compiler_diagnostic():
                for _ in range(20):
                    for message in notifications:
                        for diagnostic in message.get("params", {}).get("diagnostics", []):
                            if diagnostic["source"] == "freak":
                                return diagnostic
                    notifications.append(messages.get(timeout=15))
                raise AssertionError(f"No compiler diagnostic in {notifications}")

            try:
                send({"id": 1, "method": "initialize", "params": {
                    "processId": None, "rootUri": None, "capabilities": {},
                    "initializationOptions": {"compilerPath": str(compiler)}}})
                capabilities = response(1)["capabilities"]
                assert "completionProvider" in capabilities
                assert capabilities["textDocumentSync"]["save"], capabilities
                send({"method": "initialized", "params": {}})
                sample = Path(temporary) / "sample.fk"
                sample.write_text(SOURCE, encoding="utf-8")
                uri = sample.as_uri()
                send({"method": "textDocument/didOpen", "params": {"textDocument": {
                    "uri": uri, "languageId": "freak", "version": 1, "text": SOURCE}}})
                send({"id": 2, "method": "textDocument/completion", "params": {
                    "textDocument": {"uri": uri}, "position": {"line": 4, "character": 2}}})
                labels = [item["label"] for item in response(2)["items"]]
                assert "while" in labels and "when" in labels, labels
                assert "pilot" not in labels, labels
                # An earlier token on the line must not narrow the filter.
                send({"id": 5, "method": "textDocument/completion", "params": {
                    "textDocument": {"uri": uri}, "position": {"line": 6, "character": 6}}})
                labels = [item["label"] for item in response(5)["items"]]
                assert "greet" in labels and "grounded pilot" in labels, labels
                send({"id": 3, "method": "textDocument/definition", "params": {
                    "textDocument": {"uri": uri}, "position": {"line": 5, "character": 2}}})
                assert response(3)["range"]["start"] == {"line": 0, "character": 5}
                diagnostic = compiler_diagnostic()
                assert diagnostic["message"] == "fixed pilot cannot be modified", diagnostic
                assert diagnostic["range"] == {"start": {"line": 2, "character": 4},
                                               "end": {"line": 2, "character": 9}}, diagnostic
                # Editing invalidates what the compiler said about the saved text.
                send({"method": "textDocument/didChange", "params": {
                    "textDocument": {"uri": uri, "version": 2}, "contentChanges": [{
                        "range": {"start": {"line": 6, "character": 6},
                                  "end": {"line": 6, "character": 6}}, "text": "e"}]}})
                for _ in range(20):
                    message = messages.get(timeout=15)
                    if message.get("method") == "textDocument/publishDiagnostics":
                        break
                assert all(d["source"] != "freak" for d in message["params"]["diagnostics"]), message
                send({"id": 4, "method": "shutdown", "params": None})
                response(4)
                send({"method": "exit", "params": None})
                assert process.wait(timeout=10) == 0
            except Exception:
                errors.seek(0)
                print(errors.read().decode(errors="replace"), file=sys.stderr)
                raise
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                process.stdin.close()
                thread.join(timeout=2)
                process.stdout.close()
    print("Packaged LSP: completion, definition, compiler diagnostics, and clean shutdown passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vsix", type=Path)
    verify(parser.parse_args().vsix)
