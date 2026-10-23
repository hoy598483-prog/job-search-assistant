"""Chrome Native Messaging host: starts the local companion service on demand."""
import json
import os
import struct
import subprocess
import sys
import threading
from pathlib import Path


def send(message):
    data = json.dumps(message, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(data)) + data)
    sys.stdout.buffer.flush()


def receive():
    header = sys.stdin.buffer.read(4)
    if len(header) != 4:
        return None
    length = struct.unpack("<I", header)[0]
    if length > 1024 * 1024:
        raise ValueError("native message too large")
    body = sys.stdin.buffer.read(length)
    if len(body) != length:
        raise ValueError("native message truncated")
    return json.loads(body.decode("utf-8"))


def main():
    root = Path(sys.executable).resolve().parent.parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    extension_id = os.environ.get("JOB_COMPANION_EXTENSION_ID", "oocaknmgbcmghiohnmkjikbaaacfmkin")
    server = None
    token = None
    try:
        while True:
            message = receive()
            if message is None:
                break
            if message.get("action") == "handshake":
                extension_id = message.get("extension_id") or extension_id
                if not extension_id:
                    send({"error": "missing extension id"})
                    continue
                if server is None:
                    from companion.server import create_server
                    server, token = create_server(extension_id, port=0, root=root)
                    threading.Thread(target=server.serve_forever, daemon=True).start()
                send({"token": token, "port": server.server_port})
            else:
                send({"error": "unsupported native action"})
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        send({"error": str(exc)})
