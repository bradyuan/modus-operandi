# MO v1 — Design (draft for sign-off)

Status: **Draft, not approved** · 2026-11-01

Replaces the prototype design. Nothing is built or deleted until the user signs off. Where this
conflicts with `AGENTS.md`, `AGENTS.md` still wins until it is updated (with approval).

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

**ChatGPT produces content. MO keeps the books. You do all evaluation.**

| Who | Does | Never does |
|---|---|---|
| **ChatGPT** | organizes replies into parts, writes drafts and A/B/C variants | relays your input, chooses profiles, moves the pipeline, evaluates |
| **MO** | shows choices, records clicks/notes/seeds verbatim, seals boxes, ranks and hands out the store, enforces the order of steps | runs checks, judges or interprets text, calls an AI |
| **You** | pick, reject, finalize, explain why, seed, choose the profile | — |

**All your input goes through the MO box** (an MO-drawn panel inside the ChatGPT chat). Clicks,
notes, seeds, and profile choices go straight to MO; ChatGPT never carries them.

## 3. Profiles

- Everything (tune boxes, seeds) belongs to exactly one profile.
- **There is no global "active profile."** Each MO box carries an ID, and MO records which profile
  you picked in that box. Follow-ups in the same chat carry the ID.
- **No recognized ID → unchosen → the box asks you to pick a profile** before anything runs.
- Rule: **when in doubt, ask.** A lost ID costs one click; a wrong profile is impossible by design.
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
- **What a pass gets from each box:** final text, your note trail, and the rejected versions
  *(assumption — confirm)*.
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

## 8. Trace (developer view)

Per output: profile, batches handed out, **initial vs final** (before/after diff), and each pass's
version. Per tune box: every round, pick, and note. Shows gaps (e.g. output started, never finished).

## 9. To verify before building

- ChatGPT Apps SDK: MO box buttons/text fields call MO **directly** (not through the model).
- Tools that only the MO box can call (hidden from the model), so ChatGPT can't seal, pick, or switch profiles.
- Size limits: how much text one pass can carry.

## 10. Still open

- [ ] Seeds: one pass (assumed) or batched like tune boxes when there are many?
- [ ] Per-box content in a pass: final + notes + rejected versions (assumed)?
- [ ] Removing a single box or seed from a profile (and from where: the `@MO profiles` box?).
- [ ] Deleting a profile: permanent, or recoverable for a while (e.g. 30 days)?
- [ ] `AGENTS.md` update to match (needs explicit approval) + decision record.
- [ ] Rebuild plan: archive prototype under a git tag (`v0-prototype`), start fresh; reuse only
      pieces that fit this design.
