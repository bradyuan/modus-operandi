# 002 — Add reading alongside writing

Date: 2026-10-30 · Status: Accepted

## Context
Supplying a writing voice alone is already covered by Claude styles, ChatGPT custom instructions, and memory.

## Decision
MO applies one persistent user profile in both directions: **reading** (explain sources in terms this user understands) and **writing** (produce prose in this user's voice).

## Why
"ELI5" is just a prompt. The thing a prompt can't do is remember what the user already knows and build on it. A shared profile that covers how you understand and how you sound is more defensible than either side alone.
