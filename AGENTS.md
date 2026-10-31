# AGENTS.md — Modus Operandi (MO)

> **Status: LOCKED.** This file is the project's source of truth. Changes require explicit human approval (see "Change control").

This is the persistent source of truth for any AI agent working in this repo. If another file (README, DESIGN.md, a conversation) conflicts with this one, **this file wins**. Flag the conflict instead of acting on the other source.

## What MO is

A persistent profile of the user, applied in two directions:

- **Reading (world → you):** explain any source in terms that make sense to *this* user, build on what they already know, and point back to the source so simplifications can be checked.
- **Writing (you → world):** turn a rough idea + data into prose in the user's own voice, without adding claims the data doesn't support.

Goal: cut ~2h of reading/synthesis and ~2h of writing down to minutes each.

## Scope

- **In scope:** reading and writing. Nothing else.
- **Out of scope:** coding enforcement (architecture rules, Claude Code hooks). It's parked. `docs/ARCHITECTURE.md` is a record, not a plan. Don't propose reviving it unless the user asks.
- **Phase:** building v0.1 (writing first). Local MCP server with `mo_write`, `mo_check`, `mo_record`.

## Core design

1. **MO is a harness, not a generator.** MO maintains and persists state (profile, cases, rules), supplies it to the host AI with workflow instructions, and verifies output with deterministic code checks. MO makes no LLM calls; the host AI does all reading and writing.
2. **Tools.** Users see `@MO read`, `@MO write`, `@MO tune`, and `@MO profile`. The first three return a kit: the relevant rules + exemplars + workflow steps. Helper tools the host calls on its own: `mo_check` (deterministic lint + voice checks), `mo_record` (logs picks/edits), `mo_calibrate` (yes/no rule suggestions). Widget buttons call tools directly.
   - `@MO profile` lists, creates, and switches profiles, and saves writing samples. The user's explicit request is the confirmation; MO rejects text matching recent drafts it checked (deterministic), so AI-written text can't drift into the profile. Samples are labeled user-provided and removable.
   - Each user's profiles are tied to their host account through one-time account linking (OAuth). In development, a secret link stands in for sign-in.
   - Drafts are shown through `mo_present`, which runs the checks itself.
   - **MO guarantees visibility, not correctness:** nothing appears in MO's UI unchecked; failures are flagged, never hidden. Retries are requested, not guaranteed.
3. **Feedback loop.** `@MO tune` → the host produces 3 variations as MO specifies, each differing in one way → the user answers `picked`, `none_fit`, or `skipped`. MO decides the next step in code, not the host: a pick moves on; `none_fit` stays on the same target with new variations (asking what's off after 2 rounds); `skipped` moves on and records no preference.
4. **Two modes.** **Use:** the profile is read-only; picks affect the current piece only. **Calibrate:** occasional yes/no questions turn repeated patterns into rule changes. Nothing changes without the user's approval.
5. **Weighting funnel:** individual cases → candidates → rules, weighted 0–1 from hits/misses (both directions). Always compact: reinforce existing rules before creating new ones. Only rules reach the context; raw cases are archived as the source of truth.
6. **Profile vs. modifiers:** the profile is who the user is (stable); modifiers (persuasive, succinct, ...) are per request and never written to the profile.
7. **Reading and writing.**
   - **Reading:** the host gathers the source broadly into a fixed schema, then shapes it using the user's rules.
   - **Writing:** voice-first. Start from the user's seed (or stored exemplars if none). Resume/notes = fact sheet; job descriptions/assignments = checklists. External text is never imitated.
   - Results come first; asking for a seed is optional.
8. **Voice evolves only through accepted suggestions.** Influences contribute techniques, never sentences, with capped weight; the base voice stays the anchor. Influence texts are private and never committed or shipped.
9. **Faithfulness over fluency.** Reading stays faithful to the source; writing never invents facts.
10. **Private by design.** Store the minimum; sources pass through. Data is encrypted, exportable, and deletable. Development runs locally (tunnel); the product is hosted.
11. **Evals.** The user's picks and edits are the ground truth, and edit distance is the north-star metric. Deterministic checks run on every output. No LLM judge in v0.1.

## Tentative (not yet decided)

- Hosting provider (Fly.io or Render)
- Exact fixed schemas for reading dumps and writing kits

**Decided:** writing ships first (tests: job applications, essays, a journal article).
Stack: Python + FastAPI + MCP SDK, Postgres, React widget, Docker, GitHub Actions CI/CD (tests + golden-set evals), OpenTelemetry. No vector database: the profile is compact enough to send whole.

## Where things live

- `README.md`: public-facing description
- `docs/DESIGN.md`: detailed design and open questions
- `docs/decisions/`: why the direction changed. Read these before re-proposing a rejected idea.
- `docs/ARCHITECTURE.md`: the parked coding-enforcement design

## Change control

- **Agents must not edit this file without explicit human approval.** Propose the change as a diff, explain why, and wait for a clear yes. Silence or ambiguity is not approval.
- Approval for one change doesn't cover the next one.
- Every approved change to "Core design" or "Scope" also gets a decision record in `docs/decisions/` (`NNN-short-title.md`: Context, Decision, Why).
- Other files (`README.md`, `docs/*`) may be edited normally, but must not contradict this file.

## Working conventions

- Keep this file to stable facts. Status and todos go elsewhere (GitHub Issues once published).
- Be candid about weak ideas and existing competitors. The user prefers honest assessment over encouragement.
