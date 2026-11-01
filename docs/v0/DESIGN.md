# MO v0 — Design (prototype)

Status: **Retired** · code under the git tag `v0-prototype` · why: [LESSONS.md](LESSONS.md)

A short summary of what the prototype was. The full code and docs are in the tag.

- **An MCP server for ChatGPT** (developer mode, cloudflared tunnel) with tools the host AI called
  itself: `mo_write` / `mo_read` returned a "kit" (rules, writing samples, steps), `mo_check` ran
  deterministic checks on drafts (AI phrases, copied phrases, unsupported numbers, voice distance),
  `mo_tune` ran A/B/C rounds, `mo_record` stored feedback, `mo_profile` managed profiles.
- **Separate reading and writing pipelines**, each with its own kit and tuning dimensions.
- **A weighting funnel:** feedback cases → candidate rules → rules weighted by hits and misses; only
  rules reached ChatGPT.
- **A global active profile** that ChatGPT could set or switch.
- **ChatGPT relayed everything:** the user's picks, notes, and samples reached MO through the AI.
- Late additions: a local trace page of every call, and a one-command dev runner.
