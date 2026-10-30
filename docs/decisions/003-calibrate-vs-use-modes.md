# 003 — Separate Calibrate and Use modes

Date: 2026-10-30 · Status: Accepted

## Context
Self-updating profiles drift: an LLM summarizing feedback can over-generalize ("disliked once" becomes "never do X").

## Decision
- **Calibrate:** calibration questions seed the profile; changes are shown as diffs and approved by the user.
- **Use:** the profile is read-only. Signals (ratings, the user's edits to drafts) are queued as suggestions for the next calibration, never applied automatically.

## Why
The profile can't drift on its own, but the best signals from real use (especially edits) aren't thrown away.
