"""MO latency benchmark: each query goes through MO end to end, with an OpenAI model standing in for ChatGPT.

    export OPENAI_API_KEY=…   (in your own shell; never in chat or the repo)
    uv run python -m bench.harness run --profile-dir bench/profiles/intuitive-reader \
        --schedule A=1,3,10,30 --schedule B=10,30,100 --model gpt-5 --limit 300
    uv run python -m bench.harness report bench/results/<file>.jsonl

What happens per query: the model gets MO's own server instructions and the query ("@MO …"),
writes its answer, calls mo_output, and follows MO's replies pass by pass (mo_output_pass), exactly
the tool loop ChatGPT runs. Every schedule runs the same query at the same time (paired), each
against its own local MO with its own copy of the frozen profile. MO's code is unchanged; only
TUNE_BATCHES differs.

Measured per run (wall clock, seconds from the query being sent):
  first_voiced  pass 1 accepted by MO (the first version in the user's voice)
  e2e           last pass accepted by MO (100% voice loaded; the window shows the final version)
plus model calls, passes, and input/output tokens. Not measured: ChatGPT's own UI and the
window's follow-up messages (they only happen when a run stalls). A run that doesn't finish is
reported as not finished, never dropped silently.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import secrets
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx

from bench.serve import BENCH_TOKEN, BENCH_USER

HERE = Path(__file__).parent
ROOT = HERE.parent
MAX_MODEL_CALLS = 40
OUTPUT_TOOLS = ("mo_output", "mo_output_pass")  # the tools of the @MO output flow
DONE_MARK = "the MO window above shows the result"  # in runs.DONE: every pass is in


# ---- MO over MCP (Streamable HTTP), as ChatGPT's app calls it ------------------------------------

class MOChat:
    """One chat with MO: every call carries the bench token and this chat's `openai/session`."""

    def __init__(self, http: httpx.AsyncClient, chat: str):
        self.http, self.chat, self.session, self.ids = http, chat, None, 0

    async def _rpc(self, body: dict) -> dict | None:
        headers = {"accept": "application/json, text/event-stream", "content-type": "application/json",
                   "authorization": f"Bearer {BENCH_TOKEN}"}
        if self.session:
            headers["mcp-session-id"] = self.session
        r = await self.http.post("/mcp", json=body, headers=headers)
        r.raise_for_status()
        self.session = self.session or r.headers.get("mcp-session-id")
        data = [json.loads(line[5:]) for line in r.text.splitlines() if line.startswith("data:")]
        if not data and r.headers.get("content-type", "").startswith("application/json") and r.text:
            data = [r.json()]
        return data[0] if data else None

    async def start(self) -> None:
        await self._rpc({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "mo-bench", "version": "1"}}})
        await self._rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

    async def tools(self) -> list[dict]:
        self.ids += 1
        res = await self._rpc({"jsonrpc": "2.0", "id": self.ids, "method": "tools/list"})
        return res["result"]["tools"]

    async def call(self, name: str, args: dict) -> tuple[str, bool]:
        self.ids += 1
        res = await self._rpc({"jsonrpc": "2.0", "id": self.ids, "method": "tools/call", "params": {
            "name": name, "arguments": args, "_meta": {"openai/session": self.chat}}})
        if "error" in res:
            return res["error"].get("message", "error"), True
        result = res["result"]
        text = "\n".join(c.get("text", "") for c in result.get("content", []))
        return text, bool(result.get("isError"))


# ---- the model standing in for ChatGPT ----------------------------------------------------------

@dataclass
class Reply:
    id: str
    calls: list[tuple[str, str, dict]]  # (call_id, tool name, arguments)
    input_tokens: int = 0
    output_tokens: int = 0


class Model(Protocol):
    name: str

    async def respond(self, instructions: str, items: list[dict], tools: list[dict],
                      previous: str | None) -> Reply: ...


class OpenAIModel:
    """OpenAI Responses API with function tools (MO's tool schemas, passed through unchanged)."""

    def __init__(self, name: str, reasoning: str | None, key: str):
        self.name, self.reasoning = name, reasoning
        self.http = httpx.AsyncClient(base_url="https://api.openai.com/v1", timeout=600,
                                      headers={"authorization": f"Bearer {key}"})

    async def respond(self, instructions, items, tools, previous):
        body: dict[str, Any] = {"model": self.name, "instructions": instructions, "input": items,
                                "tools": tools, "store": True}
        if previous:
            body["previous_response_id"] = previous
        if self.reasoning:
            body["reasoning"] = {"effort": self.reasoning}
        for attempt in range(5):
            r = await self.http.post("/responses", json=body)
            if r.status_code not in (429, 500, 502, 503) or attempt == 4:
                break
            await asyncio.sleep(2 ** attempt * 5)  # rate limit / outage: wait, then retry the same call
        r.raise_for_status()
        data = r.json()
        calls = [(o["call_id"], o["name"], json.loads(o["arguments"] or "{}"))
                 for o in data.get("output", []) if o.get("type") == "function_call"]
        usage = data.get("usage") or {}
        return Reply(data["id"], calls, usage.get("input_tokens", 0), usage.get("output_tokens", 0))


def as_function_tools(mcp_tools: list[dict]) -> list[dict]:
    return [{"type": "function", "name": t["name"], "description": t.get("description", ""),
             "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}}
            for t in mcp_tools if t["name"] in OUTPUT_TOOLS]


# ---- one run ------------------------------------------------------------------------------------

@dataclass
class Result:
    query: str
    schedule: str
    model: str
    status: str = "not_finished"   # finished | not_finished | error
    e2e: float | None = None
    first_voiced: float | None = None
    initial: float | None = None   # mo_output accepted (ChatGPT's normal answer written)
    passes: int = 0
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    refusals: int = 0
    error: str | None = None
    started: float = field(default_factory=time.time)


async def run_one(query: dict, schedule: str, mo: MOChat, model: Model, instructions: str,
                  tools: list[dict]) -> Result:
    res = Result(query=query["id"], schedule=schedule, model=model.name)
    t0 = time.perf_counter()
    since = lambda: round(time.perf_counter() - t0, 3)  # noqa: E731
    try:
        reply = await model.respond(instructions, [{"role": "user", "content": query["query"]}], tools, None)
        while True:
            res.model_calls += 1
            res.input_tokens += reply.input_tokens
            res.output_tokens += reply.output_tokens
            if not reply.calls:
                return res   # the model stopped before MO was done: not finished
            outputs = []
            for call_id, name, args in reply.calls:
                text, failed = await mo.call(name, args)
                if failed:
                    res.refusals += 1
                elif name == "mo_output":
                    res.initial = since()
                elif name == "mo_output_pass":
                    res.passes += 1
                    res.first_voiced = res.first_voiced or since()
                if not failed and DONE_MARK in text:
                    res.status, res.e2e = "finished", since()
                    return res
                outputs.append({"type": "function_call_output", "call_id": call_id, "output": text})
            if res.model_calls >= MAX_MODEL_CALLS:
                res.error = f"stopped after {MAX_MODEL_CALLS} model calls"
                return res
            reply = await model.respond(instructions, outputs, tools, reply.id)
    except Exception as exc:  # noqa: BLE001 — recorded, never hidden
        res.status, res.error = "error", f"{type(exc).__name__}: {exc}"[:300]
        return res


# ---- the full benchmark -------------------------------------------------------------------------

def set_voice(home: Path, chat: str, profile: str) -> None:
    """The chat's voice, as if the user had picked it in an MO window (the bench user's own store)."""
    os.environ["MO_HOME"] = str(home)
    from mo import chats, events
    with events.as_user(BENCH_USER):
        chats.set_voice(chat, profile)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def wait_up(url: str) -> None:
    async with httpx.AsyncClient() as http:
        for _ in range(100):
            try:
                await http.get(url + "/mcp")
                return
            except httpx.TransportError:
                await asyncio.sleep(0.1)
    raise RuntimeError(f"MO didn't start at {url}")


async def run_all(args: argparse.Namespace, model: Model) -> Path:
    base = Path(args.out_dir)
    profile_dir = Path(args.profile_dir)
    profile = profile_dir.name
    queries = [json.loads(line) for line in Path(args.queries).read_text().splitlines() if line.strip()][: args.limit]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = base / "results" / f"{stamp}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if getattr(args, "resume", None):
        # Keep every query that finished on all schedules; re-run the rest (both schedules again, paired).
        old = [json.loads(line) for line in Path(args.resume).read_text().splitlines()[1:] if line.strip()]
        labels = {spec.split("=", 1)[0] for spec in args.schedule}
        whole = {q for q in {r["query"] for r in old}
                 if {r["schedule"] for r in old if r["query"] == q and r["status"] == "finished"} >= labels}
        kept = [json.dumps(r) for r in old if r["query"] in whole]
        queries = [q for q in queries if q["id"] not in whole]
        print(f"resuming {args.resume}: keeping {len(whole)} finished queries, re-running {len(queries)}", flush=True)

    servers, procs = {}, []
    try:
        for spec in args.schedule:
            label, batches = spec.split("=", 1)
            home = base / "work" / stamp / label
            shutil.copytree(profile_dir, home / "users" / BENCH_USER / "profiles" / profile)
            port = free_port()
            procs.append(subprocess.Popen(
                [sys.executable, "-m", "bench.serve", "--port", str(port), "--home", str(home), "--batches", batches],
                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=(base / "work" / stamp / f"{label}.log").open("w")))
            servers[label] = (home, f"http://127.0.0.1:{port}", batches)
        for _, url, _ in servers.values():
            await wait_up(url)

        meta = {"meta": {"model": model.name, "reasoning": getattr(model, "reasoning", None), "profile": profile,
                         "schedules": {k: v[2] for k, v in servers.items()}, "queries": args.queries,
                         "count": len(queries) + len(kept) // max(1, len(servers)), "concurrency": args.concurrency,
                         "started": stamp, **({"resumed_from": str(args.resume)} if kept else {})}}
        out.write_text(json.dumps(meta) + "\n" + "".join(line + "\n" for line in kept))
        gate = asyncio.Semaphore(args.concurrency)
        rng = random.Random(stamp)
        done = 0

        async def one_query(q: dict) -> None:
            nonlocal done
            async with gate:
                labels = list(servers)
                rng.shuffle(labels)  # who calls the API first doesn't favor one schedule

                async def one(label: str) -> Result:
                    home, url, _ = servers[label]
                    chat = f"bench-{label}-{q['id']}-{secrets.token_hex(3)}"
                    set_voice(home, chat, profile)
                    async with httpx.AsyncClient(base_url=url, timeout=60) as http:
                        mo = MOChat(http, chat)
                        await mo.start()
                        tools = as_function_tools(await mo.tools())
                        return await run_one(q, label, mo, model, args.instructions, tools)

                results = await asyncio.gather(*(one(label) for label in labels))
                with out.open("a") as f:
                    for r in results:
                        f.write(json.dumps(r.__dict__) + "\n")
                done += 1
                line = " · ".join(f"{r.schedule}: {r.status} {r.e2e or '-'}s {r.passes}p" for r in results)
                print(f"[{done}/{len(queries)}] {q['id']}  {line}", flush=True)

        await asyncio.gather(*(one_query(q) for q in queries))
    finally:
        for p in procs:
            p.terminate()
    return out


# ---- report -------------------------------------------------------------------------------------

def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (no interpolation): a value that actually happened."""
    if not values:
        return None
    ranked = sorted(values)
    return ranked[max(0, -(-len(ranked) * p // 100) - 1)]


def report(path: Path) -> str:
    lines = path.read_text().splitlines()
    meta = json.loads(lines[0])["meta"]
    rows = [json.loads(line) for line in lines[1:] if line.strip()]
    labels = list(meta["schedules"])
    out = [f"model {meta['model']} (reasoning {meta['reasoning']}) · profile {meta['profile']} · "
           f"{meta['count']} queries from {meta['queries']}", ""]
    head = f"{'schedule':<16}{'finished':>10}{'p50':>9}{'p95':>9}{'p99':>9}{'first p50':>11}{'passes':>8}{'calls':>7}{'out tok':>9}"
    out.append(head)
    stats = {}
    for label in labels:
        mine = [r for r in rows if r["schedule"] == label]
        ok = [r for r in mine if r["status"] == "finished"]
        e2e = [r["e2e"] for r in ok]
        first = [r["first_voiced"] for r in ok if r["first_voiced"] is not None]
        mean = lambda k: sum(r[k] for r in ok) / len(ok) if ok else 0  # noqa: E731
        s = {p: percentile(e2e, p) for p in (50, 95, 99)}
        stats[label] = s
        fmt = lambda v: f"{v:.1f}s" if v is not None else "-"  # noqa: E731
        out.append(f"{label + ' ' + meta['schedules'][label]:<16}{len(ok):>5}/{len(mine):<4}"
                   f"{fmt(s[50]):>9}{fmt(s[95]):>9}{fmt(s[99]):>9}{fmt(percentile(first, 50)):>11}"
                   f"{mean('passes'):>8.1f}{mean('model_calls'):>7.1f}{mean('output_tokens'):>9.0f}")
    if len(labels) == 2:
        a, b = (stats[x] for x in labels)
        out.append("")
        for p in (50, 95, 99):
            if a[p] and b[p]:
                change = 100 * (a[p] - b[p]) / a[p]
                out.append(f"p{p}: {a[p]:.1f}s → {b[p]:.1f}s ({abs(change):.0f}% {'faster' if change >= 0 else 'slower'})")
    errors = [r for r in rows if r["status"] != "finished"]
    if errors:
        out.append(f"\n{len(errors)} runs didn't finish (counted, not hidden): "
                   + ", ".join(sorted({(r['error'] or r['status'])[:60] for r in errors})[:5]))
    return "\n".join(out)


def mo_instructions() -> str:
    """MO's own server instructions: what ChatGPT is told when it connects."""
    from bench.serve import BenchVerifier
    from mo.server import create_server
    return create_server("http://127.0.0.1", verifier=BenchVerifier()).instructions


def main() -> None:
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="MO latency benchmark")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--profile-dir", required=True, help="a frozen copy of one profile's folder")
    run.add_argument("--schedule", action="append", required=True, help="LABEL=batches, e.g. A=1,3,10,30")
    run.add_argument("--queries", default=str(HERE / "queries.jsonl"))
    run.add_argument("--limit", type=int, default=300)
    run.add_argument("--model", default="gpt-5")
    run.add_argument("--reasoning", default="low", help="reasoning effort, or '' for non-reasoning models")
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument("--out-dir", default=str(HERE), help="results/ and work/ go here")
    run.add_argument("--resume", help="an earlier results file: keep its finished queries, re-run the rest")
    rep = sub.add_parser("report")
    rep.add_argument("path")
    args = parser.parse_args()
    if args.cmd == "report":
        print(report(Path(args.path)))
        return
    env = ROOT / ".env"  # gitignored; KEY=value lines
    for line in env.read_text().splitlines() if env.exists() else []:
        name, _, value = line.partition("=")
        if name.strip() and not line.lstrip().startswith("#"):
            os.environ.setdefault(name.strip(), value.strip().strip('"'))
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("Set OPENAI_API_KEY in your shell first (never paste it into chat or the repo).")
    args.reasoning = args.reasoning or None
    args.instructions = mo_instructions()
    path = asyncio.run(run_all(args, OpenAIModel(args.model, args.reasoning, key)))
    print("\n" + report(path) + f"\n\nraw: {path}")


if __name__ == "__main__":
    main()
