# AGENTS.md — Modus Operandi (MO)

> **Status: LOCKED.** This file is the project's source of truth. Changes require explicit human approval (see "Change control").

This is the persistent source of truth for any AI agent working in this repo. If another file (README, a version's DESIGN.md, a conversation) conflicts with this one, **this file wins**. Flag the conflict instead of acting on the other source.

## What MO is

A persistent store of the user's own judgments (seeds and tunes), per profile, that the host AI
(ChatGPT) must work through before the user sees any output. Reading and writing are the same
thing: output. An explanation and an essay go through the same pipeline.

Goal: cut ~2h of reading/synthesis and ~2h of writing down to minutes each.

## Scope

- **In scope:** shaping AI output (explanations and writing). Nothing else.
- **Phase:** finishing v1 (`docs/v1/DESIGN.md`, `docs/v1/HOSTING.md`): MO hosted on Fly.io
  for many users, with WorkOS sign-in, connected in ChatGPT developer mode.

## Core design

1. **ChatGPT produces content. MO keeps the books. The user does all evaluation.** MO runs no
   checks, interprets no text, and makes no AI calls.
2. **Commands:** `@MO` + anything (output), `@MO help`, `@MO config` (also plain `@MO` and
   `@MO profile`), `@MO seed`, `@MO tune` (also "Tune voice profile" under an output),
   `@MO trace` (also `@MO debug`). Windows: Help, Config, Output, Tune, Trace.
3. **User input goes only through the MO box**, straight to MO, signed with a per-box key ChatGPT
   can't see. ChatGPT has no tools that record evaluations or manage profiles. Typed answers in
   the chat don't count.
4. **Tuning:** each tuning is its own box (A/B/C per part, rounds locked once shown). Only the
   user's ✓ seals a box; the whole box goes to the profile's long-term store immediately, verbatim.
   No compaction.
5. **Seeding:** the user pastes a perfect example into the MO box; stored verbatim. Seeds from other
   authors are allowed, stay private, and are never committed or shipped.
6. **Output:** seeds first, then tune boxes ranked by rounds (most first), in passes of 1, 3, 10, 30, …
   Each pass gets the initial response, the current version, and its batch. The MO window always
   shows the best version so far (availability over consistency) with "x% voice loaded" (the share
   of the voice's seed words already passed through). Below 100%, a stalled run offers
   "Continue?"; continuing is the user's click, and MO never retries on its own. At 100%, the
   window offers "Not satisfied? Tune voice profile". A partial result can never look complete.
7. **Voice per chat:** each chat has one current profile, its voice, keyed by the user and the chat
   ID that ChatGPT's app attaches to every call (never relayed by the model). It is used for output and is
   the profile Config works on. Only the HUMAN USER sets it, in an MO box in that chat: Config's
   Profiles tab, the Output window, or the prompt on a chat's first output. It stays fixed until
   they change it. Nothing is inherited from other chats. Each result is labeled with the voice it
   was written in.
8. **Deterministic where MO acts, visible where ChatGPT acts.** MO guarantees its state, the order
   of steps, and visibility of gaps, not the quality of ChatGPT's writing. The user's picks are the gate.
9. **Observability:** an append-only event log tagging every event HUMAN USER / CHATGPT / MO / DEV;
   OpenTelemetry traces with IDs and counts only; deterministic alarms. Each user sees their own
   full trace (`@MO trace` or the trace page, same sign-in as ChatGPT). Admins (verified emails,
   kept outside the repo) see every user's full data and trace, read-only.
10. **Private by design.** Store the minimum; data is exportable and deletable. MO runs only
    hosted, reached through ChatGPT; there is no local mode.
11. **Evals:** the user's picks are the only ground truth. North-star metric: rounds until ✓,
    falling over time. No LLM judge and no MO checks.
12. **Users:** 1 global → N users → N profiles each, for data and trace alike. Sign-in is OAuth 2.1
    (WorkOS AuthKit) through ChatGPT's "Connect"; every call is scoped to the token's user, and each
    MO window is bound to the user of the call that opened it. A user never sees another user's data.
    Deleting an account takes two clicks, is permanent, and wipes that user's folder. Each user may
    store up to 50 MB.

## Tentative (not yet decided)

- Packaging as a ChatGPT plugin

**Decided stack:** Python + MCP SDK, ChatGPT Apps SDK (the MO box), Docker, Fly.io (one machine and
a volume: centralized compute and storage as JSON files per user), WorkOS AuthKit (OAuth 2.1),
GitHub Actions CI, OpenTelemetry. Postgres only when needed. No vector database.

## Where things live

- `README.md`: setup and public-facing description
- `docs/vN/DESIGN.md` and `docs/vN/LESSONS.md`: each version's design and what it taught us. The
  highest N is current. Read earlier versions' LESSONS.md before re-proposing an idea.

## Change control

- **Agents must not edit this file without explicit human approval.** Propose the change as a diff, explain why, and wait for a clear yes. Silence or ambiguity is not approval.
- Approval for one change doesn't cover the next one.
- Every approved change to "Core design" or "Scope" also gets a dated entry in the current
  version's LESSONS.md. A version's DESIGN.md is frozen once building starts; resetting to a new
  version (complete rebuild) needs explicit approval and gets a git tag.
- Other files (`README.md`, `docs/*`) may be edited normally, but must not contradict this file.

## Working conventions

- Keep this file to stable facts. Status and todos go elsewhere (GitHub Issues once published).
- Be candid about weak ideas and existing competitors. The user prefers honest assessment over encouragement.
