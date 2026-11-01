# MO v1 — Design

Status: **Approved** · 2026-11-01 · frozen once building starts · log: [LESSONS.md](LESSONS.md)

Replaces [v0](../v0/DESIGN.md), which hit its limit for the reasons in [v0 lessons](../v0/LESSONS.md).

## 1. What MO is, from the user's side

You talk to ChatGPT. MO makes ChatGPT's output come out the way **you** like it, using a store of
your own judgments. There is no reading/writing split: everything ChatGPT produces is output.

| Command | You do | MO stores |
|---|---|---|
| **`@MO`** (Output) | ask for anything | nothing — it **reads** the store |
| **`@MO tune`** (Tuning) | pick between A / B / C until it's right | one sealed **tune box**: every version, pick, and note |
| **`@MO seed`** (Seeding) | paste a perfect example (yours, or e.g. a Hemingway excerpt) | one **seed**, exactly as pasted |
| **`@MO profiles`** | see your profiles; create or delete one | the profile list |

Analogy: tuning and seeding fill a photo album; output is the barber reading the album before cutting.

## 2. The rule that shapes everything

**ChatGPT produces content. MO keeps the books. The HUMAN USER does all evaluation.**

MO recognizes exactly four actors, and every event it records names one of them:

| Actor | Who | How MO knows |
|---|---|---|
| **HUMAN USER** | the person using MO | only a call over the MO box's direct line, signed with that box's key |
| **CHATGPT** | the host AI | an ordinary tool call |
| **MO** | MO's own code | internal (batching, sealing, refusals) |
| **DEV** | the developer, while debugging | a dev-only endpoint on this computer (§9.6) |

Nothing else counts as the HUMAN USER: not text typed in the chat, not anything ChatGPT relays.

| Who | Does | Never does |
|---|---|---|
| **ChatGPT** | organizes replies into parts, writes drafts and A/B/C variants | relays your input, chooses profiles, moves the pipeline, evaluates |
| **MO** | shows choices, records clicks/notes/seeds verbatim, seals boxes, ranks and hands out the store, enforces the order of steps | runs checks, judges or interprets text, calls an AI |
| **HUMAN USER** | pick, reject, finalize, explain why, seed, choose the profile | — |

**All your input goes through the MO box** (an MO-drawn panel inside the ChatGPT chat). Clicks,
notes, seeds, and profile choices go straight to MO; ChatGPT never carries them.

## 3. Profiles

- Everything (tune boxes, seeds) belongs to exactly one profile.
- **There is no global "active profile."** Each MO box carries an ID, and MO records which profile
  you picked in that box. Follow-ups in the same chat carry the ID.
- **No recognized ID → unchosen → the box asks you to pick a profile** before anything runs.
- **Stale-ID rule:** boxes in a chat form a chain, and MO accepts only the **latest** box's ID. An
  older (valid but stale) ID is treated as unrecognized → ask. So ChatGPT can't reuse an earlier
  box to slip back to a profile you switched away from.
- Rule: **when in doubt, ask.** A lost ID costs one click; a wrong profile is impossible by design.
- **Every MO box shows its profile as a large label** ("Tuning · eli5-reader", "Output ·
  job-apps"), so the profile in use is never in question.
- Multiple chats can't interfere: there's no shared setting to overwrite.

**`@MO profiles`** opens an MO box listing your profiles, each with its counts (seeds, sealed
tune boxes). Everything happens by clicks and fields in the box, never through ChatGPT:

| Action | In the MO box |
|---|---|
| **List** | shown on open: name · seeds · tune boxes · last used |
| **Create** | type a name → **Create** |
| **Delete** | **Delete** → the box asks you to confirm with a second click showing what will be lost ("eli5-reader: 2 seeds, 7 tune boxes") |

ChatGPT has no way to create, delete, or pick a profile.

## 4. Tuning (`@MO tune`) — writes to the store

```
you: @MO tune <this part>            (ChatGPT decides the parts: intro, sections, …)
ChatGPT writes A / B / C  ──► MO box shows them in arrival order (order means nothing)
you: pick A/B/C or "None of these"; then ✓ Final or ↻ Keep tuning; optional "why not perfect?"
↻ → ChatGPT gets THIS box's history + your note → new A / B / C → repeat
✓ → box sealed → moved to the profile's long-term store immediately
```

- **One tuning = one box**, own ID, never mixed with other boxes while open. Several can be open
  at once (even across chats).
- **Only your ✓ seals a box.** Unsealed boxes never reach long-term.
- **Part position is recorded by MO** in arrival order (part 1, 2, …). ChatGPT's own labels are
  stored as text but never acted on.

**A sealed box stores everything, verbatim:**
```
box 7f3a · profile eli5-reader · part 1 · target: "<what was being tuned>"
  round 1: A/B/C texts · you picked B · ↻ · note "too abstract"
  round 2: A/B/C texts · you picked A · ↻ · note "closer, cut the jargon"
  round 3: A/B/C texts · you picked C · ✓
  rounds: 3 · sealed: 2026-11-01T14:02
```

## 5. Seeding (`@MO seed`) — writes to the store

- You paste the text **into the MO box** (not the chat), so it arrives byte for byte.
- Stored as-is under the chosen profile. No checks, no edits.
- Tip, not a rule: a Hemingway seed in *your* profile blends his voice into everything; a separate
  profile keeps them apart.

## 6. Output (`@MO`) — reads the store

```
ChatGPT writes its INITIAL response
pass 0:  seeds                       ┐
pass 1:  tune boxes 1–3              │  each pass gets exactly:
pass 2:  tune boxes 4–10             │   • the INITIAL response   (anchors what is said)
pass 3:  tune boxes 11–30            │   • the CURRENT version    (carries what's learned)
…        until every box is used     ┘   • this pass's batch only
→ the CURRENT version after the last pass appears in the MO box
```

- **Ranking (fixed code):** seeds first; then tune boxes by **number of rounds, most first**
  (a 10-round box holds 9 corrections in your words); ties → newest first.
- **Batch cut points (fixed code):** 3, 10, 30, 100, … (cumulative cut points; each pass gets only
  the boxes new since the previous cut).
- **What a pass gets from each box:** final text, your note trail, and the rejected versions.
- **Seeds:** one pass; batched like tune boxes (3, 10, 30, …) only if they don't fit in one.
- **Pass enforcement:** ChatGPT receives batch *k+1* only after handing MO the version from
  pass *k*. MO shows the output **only after the last pass**. Skipping passes means no MO box —
  visibly missing.
- Same profile + same store → same batches, every time.

## 7. What's deterministic and what isn't

| Step | Deterministic? |
|---|---|
| Your clicks, notes, seeds, profile choice reaching MO | ✅ direct from the MO box |
| Opening/sealing boxes, storing, ranking, batching | ✅ MO's code |
| Pass order; output only after the last pass | ✅ MO refuses out-of-order steps |
| Whether ChatGPT starts at all / writes good content | ❌ ChatGPT — visible if skipped (no MO box) |
| Whether ChatGPT actually uses each batch | ❌ ChatGPT — your tuning is the gate |

**Guarantee:** nothing reaches the store without your action, the right data always reaches
ChatGPT in the right order, and nothing appears in the MO box out of order. **Not guaranteed:**
ChatGPT's writing quality. Measure whether the store helps by **rounds until ✓** per tune box over
time — a count, not an evaluation.

## 8. Security: the MO box's direct line to MO

ChatGPT must never be able to pick, seal, note, seed, or manage profiles, or pretend to be you.

```
MO ──tool result──► ChatGPT ──► draws the MO box (MO's own code; ChatGPT can't change it)
   └─ hidden field (_meta): per-box secret key — the box sees it, ChatGPT doesn't
you click / type in the box ──HTTPS, signed with the key──► MO   (ChatGPT never relays it)
```

- **ChatGPT has no eval tools.** Its tools only submit content (variants, pass versions). Picks,
  ✓ / ↻, notes, seeds, and profile actions exist only behind the box's direct line.
- **Every eval call must carry its box's key**; anything else is refused and logged.
- **The key never goes anywhere ChatGPT can read** (e.g. not into the box's saved state).
- **Locked rounds:** a round's A / B / C can't be replaced once shown; a new set is accepted only
  after your ↻.
- **Influence can't be blocked, only made obvious.** ChatGPT can comment beside the box, write
  lopsided variants, or post a second reply. Every box carries its profile label and the line
  *"Only what's in this box uses your profile."*
- **Pass counts are shown in the output box** as plain facts, e.g. *"4 passes · pass 3 changed
  nothing"* (a count, not a judgment).
- **Typed answers don't count.** The box says so; there's no tool that could relay them.

## 9. Observability

MO only keeps books, so **every state change is an event, and the event log is the
observability.** The rest is views over it.

### 9.1 The event log (source of truth)

Append-only, per profile. The store (seeds, sealed boxes) is derived from it. Every event records
**who caused it**:

| Actor | How MO knows | Examples |
|---|---|---|
| **HUMAN USER** | a call over the box's direct line with a valid key | picked B, ↻ with note, ✓, seed added, profile created / deleted / chosen |
| **CHATGPT** | an ordinary tool call | variants submitted for round 2, pass 3 version submitted, output started |
| **MO** | MO's own code | batch 2 handed out (boxes 4–10), round locked, box sealed, **request refused** (and why) |

Filtering by actor answers "did ChatGPT touch my evals?" directly: **every HUMAN USER event must come
from the box line; any eval-type event from CHATGPT is impossible by design, and any attempt
appears as a refusal.**

### 9.2 Traces (OpenTelemetry)

- **One trace per output:** spans for the initial response → pass 0 (seeds) → pass 1…n (batch
  sizes, box IDs used) → shown in the MO box.
- **One trace per tune box:** a span per round (variants in, your pick, note, ↻ / ✓).
- **Spans carry IDs and counts only, never your text**, so they can go to any OpenTelemetry backend
  safely; the text stays in MO's store.

### 9.3 Invariant alarms (deterministic)

Computed from the event log; each is a fact, not a judgment:

| Alarm | Means |
|---|---|
| Eval call without a valid key | something other than the box tried to act as you |
| Stale box ID refused | ChatGPT reused an old box (wrong-profile attempt or slip) |
| Variants resubmitted for a locked round | an attempt to change what you're choosing from |
| Output started, never shown | ChatGPT skipped or abandoned the passes |
| Pass submitted unchanged | a pass may have been faked (count shown, not judged) |
| Pass out of order | ChatGPT tried to skip a batch (refused) |

### 9.4 Metrics (counts only)

- ⭐ **Rounds until ✓** per tune box over time — falls if the store is helping.
- Passes per output; passes that changed nothing.
- Tune boxes opened vs sealed; outputs started vs shown.
- Refusals by type.

### 9.5 Views

- **Trace page** (local, this computer only): per output, **initial vs final** diff plus each
  pass; per tune box, every round; per profile, the store and its changelog; an alarms panel.
  Every row shows its actor (HUMAN USER / CHATGPT / MO / DEV).
- Later, any OpenTelemetry backend (e.g. Jaeger, Grafana) for the ID-and-count traces.

### 9.6 Developer access (dev mode only, this computer only)

For debugging and iterating. Served only when MO runs in dev mode, and only to `127.0.0.1`
(never through the tunnel).

| Endpoint | Gives |
|---|---|
| `/trace` | the trace page (§9.5) |
| `/trace/events` | the event log as JSON, filterable by profile, actor, box, type, time |
| `/trace/events/stream` | live events as they happen (watch a ChatGPT session in real time) |
| `/trace/profiles/<name>` | a profile's store: seeds, sealed boxes, counts |
| `/trace/boxes/<id>` | one box: every round, pick, note, its profile and chain |
| `/trace/alarms` | current invariant alarms |
| `/trace/box/<id>/preview` | render a box exactly as ChatGPT would, to iterate on its look |

Read-only by default. Any developer action that changes state (e.g. simulate a click to test a
flow) is recorded as actor **DEV**, never HUMAN USER, so test data can't pass for the human user's evals.

### 9.7 What can't be observed

If ChatGPT never calls MO, MO sees nothing. That gap is visible to you (no MO box) but not in the log.

## 10. To verify before building (prototype step 1)

- **`_meta` is hidden from ChatGPT:** put a test key there, ask ChatGPT what the tool result
  contains; it must not be able to recite the key.
- **The box can call MO directly** over HTTPS (`connect_domains`), with MO's domain allowlisted.
- **Allowlist with a changing tunnel:** MO serves the box itself, so on each start it can allowlist
  the current tunnel address. Check ChatGPT picks up the new allowlist after "Refresh" (if not,
  use a named Cloudflare tunnel with a fixed address).
- Size limits: how much text one pass can carry.

## 11. Still open

- [ ] Removing a single tune box or seed from a profile (proposed: in the `@MO profiles` box).
- [ ] Deleting a profile: permanent, or recoverable for a while (e.g. 30 days)?
