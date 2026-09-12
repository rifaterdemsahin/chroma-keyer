#!/usr/bin/env python3
"""Serve this repo on localhost so the browser can reach local libraries.

file:// cannot reliably play the keyed WebM or list output/logs.
Bind 127.0.0.1 only — this is a local library, not a public host.
"""

from __future__ import annotations

import argparse
import http.server
import os
import socket
import socketserver
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8876


def pick_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 24):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise SystemExit(f"No free TCP port in {preferred}-{preferred + 23} on {host}")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write(f"[local] {self.address_string()} {fmt % args}\n")
        sys.stdout.flush()


def open_chrome(url: str) -> None:
    try:
        subprocess.run(["open", "-a", "Google Chrome", url], check=False)
    except OSError:
        subprocess.run(["open", url], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Localhost docs + output/logs library.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--open", action="store_true", help="Open process.html in Google Chrome")
    args = parser.parse_args()

    os.chdir(ROOT)
    port = pick_port(args.host, args.port)
    httpd = socketserver.ThreadingTCPServer((args.host, port), Handler)
    httpd.allow_reuse_address = True
    base = f"http://{args.host}:{port}"
    print("Local library server (127.0.0.1 only)", flush=True)
    print(f"  Home     {base}/", flush=True)
    print(f"  Process  {base}/process.html", flush=True)
    print(f"  Output   {base}/output.html", flush=True)
    print(f"  Clips    {base}/output/", flush=True)
    print(f"  Demo     {base}/demo/", flush=True)
    print(f"  Logs     {base}/logs/", flush=True)
    print(f"  Inbox    {base}/input/", flush=True)
    print("Ctrl+C to stop.", flush=True)
    if args.open:
        open_chrome(f"{base}/process.html")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
        return 0
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
