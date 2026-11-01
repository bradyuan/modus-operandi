# 001 — Base design: tune and seed into your voice, MO keeps the books

Status: Accepted · 2026-11-01

## Context

MO is a tuning and editing loop that iterates ChatGPT's output into the user's preferred voice.
A first prototype (git tag `v0-prototype`) was tested in ChatGPT. It stored feedback but enforced
nothing: the profile it sent was empty, turning feedback into rules depended on ChatGPT choosing
to do it (it didn't), its checks passed with nothing to compare against, and the user's voice
drifted over long chats. Every fix asked the AI to cooperate. The prototype trusted the LLM inside
its own data pipeline.

## Decision

Build to [DESIGN-v1](../DESIGN-v1.md):

- **ChatGPT produces content; MO keeps the books; the user does all evaluation.** MO runs no
  checks, interprets no text, and makes no AI calls.
- Commands: `@MO` (output), `@MO tune`, `@MO seed`, `@MO profiles`. Explanations and writing are
  the same thing: output.
- **Tuning:** A/B/C per part; each tuning is its own box; only the user's ✓ seals it, and the whole
  box goes to the profile's long-term store immediately. No compaction.
- **Output:** seeds first, then tune boxes ranked by rounds (most first), in passes of 3, 10, 30, …;
  each pass gets the initial response, the current version, and its batch; the result appears in
  the MO box only after the last pass.
- **User input goes only through the MO box**, straight to MO, signed with a per-box key ChatGPT
  can't see. ChatGPT has no tools that record evaluations or manage profiles.
- **Profiles:** no global active profile; each box carries its profile; stale or unknown IDs → ask.
- **Observability:** an append-only event log tagging every event HUMAN USER / CHATGPT / MO / DEV,
  OpenTelemetry traces with IDs and counts only, deterministic alarms, and a local trace page.

## Why

A harness that trusts the model can't guarantee anything. MO can make its own state deterministic
and its process enforceable, and make every gap visible; it can't make ChatGPT write well, so the
user's picks are the gate. Storing whole tuning runs instead of AI-written summaries keeps the
store the user's own judgments, and avoids compaction, which can't be done without an AI.

## Rejected (don't re-propose without new evidence)

- **AI-written rules or summaries in the store** (asking the host to "promote" feedback): the
  host skips it, and its wording isn't the user's.
- **MO-side checks or scoring** of drafts (AI-phrase lists, voice distance, best-of-N selection by
  MO): MO doesn't evaluate; the user does.
- **Compaction** of the store: deciding that two pieces of feedback mean the same thing needs an AI.
- **A global active profile** and **profile choice by the host:** they cause wrong-profile use.
- **Separate reading and writing pipelines:** both are output.
- **A vector database / RAG:** retrieval is a fixed ranking by rounds, not similarity search.
- **Custom GPTs with Actions:** being retired by OpenAI; MCP is the path to ChatGPT plugins.
