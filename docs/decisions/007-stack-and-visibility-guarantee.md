# 007 — Stack, no RAG, and the visibility guarantee

Date: 2026-10-30 · Status: Accepted

## Context
- The stack had to be chosen.
- pgvector/RAG was considered for retrieving exemplars.
- MO doesn't control the host's generation loop, so it can't guarantee retries or correct output.

## Decision
- **Stack:** Python + FastAPI + MCP SDK, Postgres, React widget, Docker, GitHub Actions CI/CD (tests + golden-set evals), OpenTelemetry. Hosting provider still open (Fly.io or Render).
- **No vector database or RAG.** Kit selection is deterministic: the key is (profile, task, register), all rules are sent ranked by weight, and the exemplars are the ones most representative of the user's style.
- **`mo_present`:** drafts reach MO's widget only through this tool, which runs the checks itself.
- **MO guarantees visibility, not correctness.** Nothing appears in MO's UI unchecked; failures are flagged, never hidden. Retries are requested, not guaranteed.

## Why
- **No RAG:** the profile is compact and user-approved, so it fits whole and retrieval adds nothing. Topic-similar exemplars could even make the host borrow their content.
- **The guarantee:** MO can only promise what it controls, which is what it shows and records. Making the display step the check turns "the host might skip checks" into "skipped checks are visible."
- **Each stack item does a real job:** Python for text analysis, FastAPI for OAuth and data endpoints, Postgres for per-user bundles, OpenTelemetry to measure whether the host follows kits, CI to run the evals on every push.
