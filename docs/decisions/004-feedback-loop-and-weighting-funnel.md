# 004 — Feedback loop and weighting funnel

Date: 2026-10-30 · Status: Accepted

## Context
MO needs a way to learn how the user likes knowledge explained (reading) and written (writing), without the profile drifting or the context growing without limit.

## Decision
- **Loop:** "I don't like this" → 3 alternatives, each differing in one way → the user picks one → that becomes an individual case. If none fit, MO offers more alternatives; rejected ones are logged as cases too.
- **Funnel:** individual cases → candidates → rules (canonical cases), weighted 0–1 from hits/misses. Always compact: reinforce or weaken existing rules before creating new ones.
- **Context:** only rules reach the model, never raw cases. Raw cases are archived on disk as the source of truth.
- **Modes:** picks affect the current conversation immediately. The persistent profile changes only when the user approves in Calibrate mode.
- **Profile vs. modifiers:** per-request modifiers (persuasive, succinct, ...) are never written to the profile.

## Why
Choosing between alternatives is low effort and gives clean preference data. Compacting into weighted rules keeps the context small and the profile easy to read. Keeping the persistent profile frozen until the user approves changes prevents drift.
