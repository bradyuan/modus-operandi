# Modus Operandi — Architecture & Trust Model

Status: Draft · Last updated: 2026-10-30

This document covers how MO enforces approved project state and why the design is shaped the way it is. For what MO is and the problem it solves, see the [README](../README.md).

Scope: the **coding** side (Claude Code). The writing side is not yet designed.

---

## 1. Core decisions

1. **The validator is independent of Claude Code.** MO's checking logic lives in a standalone tool. Claude Code is one integration among several, never the source of enforcement.
2. **Changing authoritative rules requires explicit human approval.** A Git commit is not approval. Claude can make commits, so approval must come from an action Claude cannot perform.

## 2. The threat model in one sentence

Claude Code runs as the developer's OS user, so **anything the developer can read or write, Claude can too**: the repo, `~/.mo`, `.claude/settings.json`, Git history.

Consequences:

- Hiding the rules file somewhere else gives no protection.
- Authority must come from a **signature Claude can't produce**, verified somewhere **Claude can't reach**.

## 3. Components

```
┌─────────────────────────── Developer machine ───────────────────────────┐
│                                                                          │
│  repo/.mo/rules.yaml      ← rules (anyone, including Claude, can edit)   │
│  repo/.mo/rules.sig       ← signature from a key that needs human        │
│                             presence (Touch ID / YubiKey tap)            │
│                                                                          │
│  mo (standalone CLI)      ← validator: deterministic, no Claude          │
│   ├─ mo check             ← called by adapters                           │
│   └─ mo approve           ← shows the rules diff, asks for Touch ID,     │
│                             writes rules.sig                             │
│                                                                          │
│  Adapters (thin, swappable):                                             │
│   ├─ Claude Code hook ──► mo check     (fast feedback, cooperative)      │
│   ├─ git pre-commit ────► mo check     (catches non-Claude edits)        │
│   └─ (other agents) ────► mo check                                       │
└──────────────────────────────────────────────────────────────────────────┘
                                   │ push
                                   ▼
┌──────────────────── CI / merge gate (off-machine) ───────────────────────┐
│  mo verify-signature   ← trusted public keys pinned HERE, not in repo    │
│  mo check              ← required status check + branch protection       │
│  → this is the real enforcement point                                    │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Validator (`mo`)

- A pure function: `(approved rules, code state) → pass | fail + explanations`.
- Deterministic by default (import graphs, path boundaries). An LLM judge is reserved for rules that can't be expressed structurally, and is never in the default path.
- Checks the **resulting state** (working tree, diff), not just the proposed action. This closes Bash-based bypasses such as `sed` or `echo >`.

### 3.2 Rules and signature

- `.mo/rules.yaml` is versioned and reviewable in the repo. Claude may edit it, but that only creates a **proposal**.
- `.mo/rules.sig` is a detached signature over the rules file.
- If the rules file and signature don't match, `mo` keeps enforcing the **last approved** rules and reports the pending change.

### 3.3 Trust root

- The list of trusted public keys **must not live in the repo**. Otherwise Claude could add its own key.
- CI: pinned in organization or repo settings, protected CI variables, or an admin-only protected location.
- Locally: tamper-evident at best (see §5).

### 3.4 Adapters

These are thin wrappers that call `mo check` and pass results back:

| Adapter | Purpose | Strength |
|---|---|---|
| Claude Code hooks | Block or explain during agent work | Cooperative (fast feedback) |
| Git pre-commit | Catch edits made outside Claude | Cooperative (skippable with `--no-verify`) |
| CI required check | Gate merges | **Enforcing** |

## 4. Approval flow

1. Claude decides the architecture needs to change and edits `rules.yaml` (or runs `mo propose`).
2. `mo check` sees unsigned rules, keeps enforcing the old approved set, and tells Claude: *"Rule change pending human approval."*
3. The developer runs `mo approve`, reviews the diff, and touches the sensor (Touch ID or a hardware key). `rules.sig` updates.
4. CI checks the signature against the pinned keys, then runs `mo check` with the new rules.

Claude can *run* `mo approve`, but it cannot satisfy the presence check.

## 5. Guarantees — stated honestly

- **Local enforcement is cooperative.** Any process running as the developer can disable hooks, skip `mo`, or remove the pre-commit hook.
  - Mitigation: Claude Code **managed settings** live in an admin-owned system path and can lock hooks so project or user config can't remove them. The specific options still need verification.
- **CI is the hard guarantee.** With a required `mo check` status and branch protection, unapproved rule changes and violations can't merge, however they got there.

## 6. Known traps (design must address)

- **Existing violations.** Real codebases already break their intended architecture. MO needs a **baseline** of known violations, or it blocks everything on day one.
- **Intermediate states.** Refactors break rules partway through. Prefer checking at the end of a turn, or warning instead of blocking, for edit-level checks.
- **False positives cause loops.** Wrong blocks make the agent thrash or work around rules. Precision matters more than recall.
- **Latency.** Hooks run on every tool call, so `mo check` must be fast (target: well under 1s).
- **Architecture inference.** The proposed model from repo analysis will often be wrong. Review and editing must be easy.

## 7. Open questions

- [ ] **Implementation language and distribution:** standalone CLI, Claude Code plugin, or both? *(next)*
- [ ] Rule format and granularity (layer boundaries, path globs, plain-English requirements?)
- [ ] First supported language(s) for import analysis
- [ ] Signing mechanism: build our own vs. reuse `ssh-keygen -Y` with FIDO `sk-` keys, Sigstore, or minisign
- [ ] Solo vs. team approval (N-of-M signers?)
- [ ] Hosted approval service: deferred; start with local signing plus CI verification
