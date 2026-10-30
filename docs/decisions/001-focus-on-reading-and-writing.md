# 001 — Focus on writing (and reading), park coding enforcement

Date: 2026-10-30 · Status: Accepted

## Context
MO started as two things: architecture enforcement for Claude Code, and voice preservation for writing.

## Decision
Park coding enforcement. Focus on the writing side, and on reading (see 002).

## Why
Most of the coding side can already be assembled from existing tools: CLAUDE.md/AGENTS.md, dependency-cruiser and similar linters, a small Claude Code hook, a CI required check, and CODEOWNERS for human approval of rule changes. Too little would be left that's unique to MO. The design is kept in `docs/ARCHITECTURE.md` in case we come back to it.
