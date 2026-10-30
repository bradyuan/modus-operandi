# 005 — The host gathers, MO shapes; writing is voice-first

Date: 2026-10-30 · Status: Accepted · Partly superseded by 006 (MO no longer generates; the host writes)

## Context
Two earlier designs failed:
1. MO reading sources itself (file access, cost), or MO only lightly filtering the host's finished explanation (it can't add back what the host left out).
2. Writing built from the resume and job description with the voice applied last. That is content-first, which produces generic, corporate prose.

## Decision
- **Reading:** the host (ChatGPT) extracts broadly into a fixed schema; MO filters and shapes it. Cutting beats adding.
- **Writing:** voice-first. The user's own words for the piece (or answers to 1–2 questions) are the seed, and MO extends them, changing as little as possible. The resume is a fact sheet; the job description or assignment is a checklist, never imitated. The host never writes prose.
- **Voice evolution:** the voice evolves only through suggestions the user accepts, including borrowed techniques from chosen influences (e.g. Gay Talese). It borrows techniques, never sentences, and the base voice stays the anchor.
- **Front end:** an MO widget in ChatGPT, for exact text, the alternatives loop, and inline editing.

## Why
Each source has one job, so external voices (corporate, generic AI, or even an admired writer's) can't take over. The user's own writing stays the starting point, and every change to the voice is the user's choice.
