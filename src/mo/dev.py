"""One command for local testing in ChatGPT: start a Cloudflare quick tunnel, then MO behind it.

Usage: uv run mo-dev [--port 8000]
The tunnel address changes on every run, so update MO's link in ChatGPT each time.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import threading

from mo import server

TUNNEL_RE = re.compile(r"https://([a-z0-9-]+\.trycloudflare\.com)")


def tunnel_host(lines) -> str | None:
    for line in lines:
        if match := TUNNEL_RE.search(line):
            return match.group(1)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MO behind a fresh Cloudflare quick tunnel.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    exe = shutil.which("cloudflared") or "/opt/homebrew/bin/cloudflared"
    tunnel = subprocess.Popen([exe, "tunnel", "--url", f"http://127.0.0.1:{args.port}", "--no-autoupdate"],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    host = tunnel_host(tunnel.stdout)
    if not host:
        tunnel.terminate()
        sys.exit("cloudflared exited without printing a tunnel address.")
    threading.Thread(target=lambda: [None for _ in tunnel.stdout], daemon=True).start()  # keep its pipe drained
    print("\nNew tunnel. In ChatGPT: Settings → Apps → MO → update the link (or delete and re-add MO) "
          "with the link below. It changes every time you run mo-dev.", flush=True)

    os.environ["MO_TRACE"] = "1"  # full traces for the local trace page
    print(f"Trace (this computer only): http://127.0.0.1:{args.port}/trace", flush=True)
    sys.argv = ["mo-server", "--transport", "http", "--port", str(args.port), "--public-host", host]
    try:
        server.main()
    finally:
        tunnel.terminate()


if __name__ == "__main__":
    main()
