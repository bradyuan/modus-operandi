"""MO on localhost for the benchmark: MO's real code, a fixed bench user, and a chosen tune schedule.

    python -m bench.serve --port 8101 --home bench/work/A --batches 1,3,10,30

Same server as production except: the sign-in token is the fixed BENCH_TOKEN (user "bench"), the
store is --home, and TUNE_BATCHES is --batches (so both schedules run side by side without
changing what's deployed).
"""

from __future__ import annotations

import argparse
import os

from mcp.server.auth.provider import AccessToken

BENCH_TOKEN, BENCH_USER = "bench-token", "bench"


class BenchVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        if token != BENCH_TOKEN:
            return None
        return AccessToken(token=token, client_id="bench", scopes=[], subject=BENCH_USER)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--batches", required=True, help="tunes per pass, e.g. 1,3,10,30")
    args = parser.parse_args()
    os.environ["MO_HOME"] = os.path.abspath(args.home)
    from mo import runs
    from mo.server import create_server
    runs.TUNE_BATCHES = tuple(int(x) for x in args.batches.split(","))
    create_server(f"http://127.0.0.1:{args.port}", verifier=BenchVerifier()).run(
        transport="streamable-http", host="127.0.0.1", port=args.port, streamable_http_path="/mcp")


if __name__ == "__main__":
    main()
