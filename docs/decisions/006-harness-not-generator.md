# 006 — MO is a harness, not a generator

Date: 2026-10-30 · Status: Accepted · Supersedes parts of 005

## Context
Decision 005 had MO generating text itself (its own LLM calls in a fresh context, "quarantine"), so that the host's long context couldn't cause drift. That meant API costs, picking a model, and a second AI company seeing user data.

## Decision
- MO only maintains and persists state (profile, cases, rules), supplies it to the host AI as **kits** (rules + exemplars + workflow steps), and verifies output with **deterministic code checks** (`mo_check`). MO makes no LLM calls.
- Tools: users see `read`, `write`, `evolve`. The host calls the helpers `mo_check`, `mo_record`, and `mo_calibrate` on its own. Widget buttons call tools directly.
- Drift is countered by **re-anchoring** (a fresh kit at the end of the context on every call) and caught by `mo_check`, instead of prevented by quarantine.
- **Private by design:** store the minimum, encrypted, exportable, and deletable. Development is local (tunnel); the product is hosted, because ChatGPT apps need a remote server and per-user sign-in.
- **Writing ships first.**
- **Evals:** the user's picks and edits are the ground truth (edit distance is the north star); deterministic checks run on every output; no LLM judge in v0.1.

## Why
It's simpler to build, has no per-call costs, works with whatever model the host uses, and keeps user data away from a second AI provider. The trade-off is weaker drift protection: drift is caught and corrected rather than made impossible. The drift test in `docs/DESIGN.md` §10 decides whether that's enough.
