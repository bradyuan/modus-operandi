# 009 — Core API with thin adapters; keep MCP as the main integration

Date: 2026-10-31 · Status: Proposed (needs approval; the user asked to explore moving away from MCP)

## Context
- The user asked to prepare for "GPT integration" and to move away from the MCP server once things work.
- ChatGPT Plus doesn't appear to include developer mode for custom MCP apps.
- OpenAI is replacing Custom GPTs with ChatGPT **plugins**, which are built on MCP. Custom GPTs reportedly retire Dec 11, 2026 (see `docs/GPT.md` for sources).

## Decision (proposed)
- **All MO logic lives in `mo.api`**, a protocol-free core: typed function signatures are the input schemas, and docstrings are the host-facing descriptions.
- **Adapters are thin:** `mo.server` (MCP, about 60 lines) and `mo.actions` (GPT Actions over FastAPI, temporary). A future integration is a new adapter, not a rewrite.
- **Keep MCP as the main integration.** Moving away from it would mean moving away from where ChatGPT plugins and Claude connectors are going.
- `mo.actions` stays only while Custom GPTs exist, as a possible way to test on Plus; delete it after retirement.

## Why
- Separating the core from the protocol makes the GPT question cheap to change later.
- The research points to MCP, not away from it, as the integration ChatGPT is moving to.
