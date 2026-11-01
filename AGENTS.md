# AGENTS.md — Modus Operandi (MO)

> **Status: LOCKED.** This file is the project's source of truth. Changes require explicit human approval (see "Change control").

This is the persistent source of truth for any AI agent working in this repo. If another file (README, DESIGN-v1.md, a conversation) conflicts with this one, **this file wins**. Flag the conflict instead of acting on the other source.

## What MO is

A persistent store of the user's own judgments (seeds and tunes), per profile, that the host AI
(ChatGPT) must work through before the user sees any output. Reading and writing are the same
thing: output. An explanation and an essay go through the same pipeline.

Goal: cut ~2h of reading/synthesis and ~2h of writing down to minutes each.

## Scope

- **In scope:** shaping AI output (explanations and writing). Nothing else.
- **Phase:** building the v1 prototype (`docs/DESIGN-v1.md`): local MCP server plus the MO box,
  behind a cloudflared tunnel, connected manually in ChatGPT developer mode.

## Core design

1. **ChatGPT produces content. MO keeps the books. The user does all evaluation.** MO runs no
   checks, interprets no text, and makes no AI calls.
2. **Commands:** `@MO` (output), `@MO tune`, `@MO seed`, `@MO profiles`.
3. **User input goes only through the MO box**, straight to MO, signed with a per-box key ChatGPT
   can't see. ChatGPT has no tools that record evaluations or manage profiles. Typed answers in
   the chat don't count.
4. **Tuning:** each tuning is its own box (A/B/C per part, rounds locked once shown). Only the
   user's ✓ seals a box; the whole box goes to the profile's long-term store immediately, verbatim.
   No compaction.
5. **Seeding:** the user pastes a perfect example into the MO box; stored verbatim. Seeds from other
   authors are allowed, stay private, and are never committed or shipped.
6. **Output:** seeds first, then tune boxes ranked by rounds (most first), in passes of 3, 10, 30, …
   Each pass gets the initial response, the current version, and its batch. The result appears in
   the MO box only after the last pass.
7. **Profiles:** no global active profile. Each box carries its profile, shown as a large label.
   Unknown or stale box IDs → ask. A wrong profile must be impossible.
8. **Deterministic where MO acts, visible where ChatGPT acts.** MO guarantees its state, the order
   of steps, and visibility of gaps, not the quality of ChatGPT's writing. The user's picks are the gate.
9. **Observability:** an append-only event log tagging every event YOU / CHATGPT / MO / DEV;
   OpenTelemetry traces with IDs and counts only; deterministic alarms; a local trace page.
10. **Private by design.** Store the minimum; data is exportable and deletable. Development runs
    locally (tunnel); the product is hosted.
11. **Evals:** the user's picks are the only ground truth. North-star metric: rounds until ✓,
    falling over time. No LLM judge and no MO checks.

## Tentative (not yet decided)

- Hosting provider; packaging as a ChatGPT plugin
- Removing single boxes or seeds; whether deleting a profile is permanent

**Decided stack:** Python + MCP SDK, ChatGPT Apps SDK (the MO box), Docker, GitHub Actions CI,
OpenTelemetry. Postgres once hosted. No vector database.

## Where things live

- `README.md`: setup and public-facing description
- `docs/DESIGN-v1.md`: the design being built
- `docs/decisions/`: why the direction changed. Read these before re-proposing a rejected idea.

## Change control

- **Agents must not edit this file without explicit human approval.** Propose the change as a diff, explain why, and wait for a clear yes. Silence or ambiguity is not approval.
- Approval for one change doesn't cover the next one.
- Every approved change to "Core design" or "Scope" also gets a decision record in `docs/decisions/` (`NNN-short-title.md`: Context, Decision, Why).
- Other files (`README.md`, `docs/*`) may be edited normally, but must not contradict this file.

## Working conventions

- Keep this file to stable facts. Status and todos go elsewhere (GitHub Issues once published).
- Be candid about weak ideas and existing competitors. The user prefers honest assessment over encouragement.
