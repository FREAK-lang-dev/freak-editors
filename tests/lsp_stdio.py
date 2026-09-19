"""Initialize the packaged Python server and request a completion over stdio."""
import argparse
import json
import queue
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path


def verify(vsix: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="freak-lsp-test-") as temporary:
        with zipfile.ZipFile(vsix) as archive:
            script = Path(temporary) / "freak_lsp.py"
            script.write_bytes(archive.read("extension/freak_lsp.py"))
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([sys.executable, "-u", str(script), "--stdio"],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
            messages = queue.Queue()

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
                raise AssertionError("Too many notifications without a response")

            try:
                send({"id": 1, "method": "initialize", "params": {"processId": None, "rootUri": None, "capabilities": {}}})
                assert "completionProvider" in response(1)["capabilities"]
                send({"method": "initialized", "params": {}})
                uri = (Path(temporary) / "sample.fk").as_uri()
                send({"method": "textDocument/didOpen", "params": {"textDocument": {
                    "uri": uri, "languageId": "freak", "version": 1, "text": "pi"}}})
                send({"id": 2, "method": "textDocument/completion", "params": {
                    "textDocument": {"uri": uri}, "position": {"line": 0, "character": 2}}})
                items = response(2)["items"]
                assert any(item["label"] == "pilot" for item in items), items
                send({"id": 3, "method": "shutdown", "params": None})
                response(3)
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
    print("Packaged LSP: initialize, pilot completion, and clean shutdown passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vsix", type=Path)
    verify(parser.parse_args().vsix)
