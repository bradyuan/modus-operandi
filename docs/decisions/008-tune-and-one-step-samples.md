# 008 — `@MO tune`, code-driven rounds, and one-step samples

Date: 2026-10-31 · Status: Accepted

## Context
In the first real test (ChatGPT developer mode):
- **Samples were never saved.** The two-step save ("confirm") depended on the host calling `confirm` later, and it never did. MO ran every draft with 0 exemplars.
- **Rejections were skipped.** When the user rejected all three variations, the host moved on to the next question instead of fixing that part.
- **"Next" and "none of these work" were treated the same.**
- The user found `evolve` too vague.

## Decision
- Rename `@MO evolve` to **`@MO tune`** (`mo_tune`). Diagnostics move from `@MO profile` into `tune` (`mode='diagnostic'`).
- **MO decides the next step in code.** The user answers `picked`, `none_fit`, or `skipped`, and MO keeps the session state: `none_fit` stays on the same target with a different dimension (asking what's off after 2 misses); `picked` and `skipped` move on; `skipped` records no preference.
- **Saving a sample is one step:** the user's explicit request is the confirmation. MO rejects text matching drafts it recently checked (hashed fingerprints, no text stored), so AI-written text can't drift into the profile.
- Failed tool calls are now logged, and `mo_write` pushes harder for the user's own words as the seed.

## Why
Anything the host has to remember or judge across turns proved unreliable. Moving flow and safety into deterministic code makes the behavior testable and predictable, and the user never has to confirm their own explicit request.
