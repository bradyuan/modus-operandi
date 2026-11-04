# MO v1 — Lessons

Dated entries while building v1: what we tried, what the human user's evals showed, and approved
changes. [DESIGN.md](DESIGN.md) stays frozen once building starts; when v1 hits its limit, the last
entry here says why, and v2 begins.

## 2026-11-01 — Design approved

- v1 design approved after v0's limit ([v0 lessons](../v0/LESSONS.md)).
- The human actor is named **HUMAN USER**; MO recognizes four actors (HUMAN USER, CHATGPT, MO, DEV).
- Docs are versioned: `docs/vN/DESIGN.md` + `docs/vN/LESSONS.md`.
- Not started: the verification spike (DESIGN §10) comes first.

## 2026-11-01 — Verification spike built (step 1)

- OpenAI's Apps SDK reference confirms a tool result's `_meta` is hidden from the model and readable
  by the box, the box can call domains MO allowlists (`_meta.ui.csp.connectDomains`), and tools can
  be limited to the app (`_meta.ui.visibility`).
- ChatGPT caches the box by URI, and the allowlist holds the changing tunnel address, so the box
  URI carries a tag of that address.
- `@MO spike` shows a test box: key in `_meta`, clicks sent straight to MO, signed. Waiting on the
  human user's test in ChatGPT.

## 2026-11-01 — Spike passed

- The MO box rendered in ChatGPT and received its key; the box's clicks reached MO directly
  through the quick tunnel (so the per-run allowlist works) and were recorded as HUMAN USER,
  exactly as clicked (C, then B).
- Key test: asked to repeat the full tool result including hidden fields, ChatGPT returned only
  the text content and said no metadata or keys reached it. Consistent with the Apps SDK docs.
- No refused calls; ChatGPT made one tool call per `@MO spike`.

## 2026-11-01 — Build step 1: profiles

- Decided: **deleting a profile is permanent**, after a second confirming click in the box. The
  confirmation code is one-time, tied to that box and that profile.
- `@MO profiles`: ChatGPT's tool takes no arguments and only opens the box; list, create, and
  delete happen over the box's signed direct line as HUMAN USER. The spike tool is retired.
- Old v0 profiles moved to `~/.mo/v0-profiles/` (not deleted; includes two of the user's essays).

## 2026-11-01 — Trace by profile; delete purges a profile's events

- Human user test of `@MO profiles` passed: create, delete (two clicks), re-create; every action
  recorded as HUMAN USER from the box; ChatGPT made one call (opening the box).
- Decided: **deleting a profile removes all of its events.** One tombstone stays in "All", naming
  the profile in `deleted_profile` (not `profile`) so a re-created profile starts with a clean tab.
- `/trace` now has tabs (All, each profile, No profile), actor filters, refusals-only, and keeps
  the view in its URL. `/trace/events?profile=<name|none>` and `/trace/profiles` for scripts.

## 2026-11-01 — Profiles step tested

- Human user tests passed: ChatGPT couldn't create a profile (it only reopened the box); invalid
  names refused with a reason; `ESSAY` saved as `essay`; duplicate refused; two-click delete purged
  each profile's events; the trace fell back to All when the open profile was deleted.
- Restart test: after a new `make run`, all 11 profiles and every event were still there. Boxes
  from the previous run couldn't reach MO (their tunnel address was gone). **With the free tunnel,
  boxes only work during the run that drew them; data persists.** Hosting or a named tunnel fixes it.
- Noted for later: with many profiles, `/trace` tabs and the profiles list get crowded (a
  dropdown with search, most recent first, planned alongside the step 2 profile picker).

## 2026-11-01 — Approved: one current profile; seed formats

- **AGENTS.md item 7 changed** (approved): one current profile, set only by the HUMAN USER from a
  dropdown in any MO box; every box shows its profile and locks it in when it opens; with none
  set, the box asks. Replaces the per-chat box chain and stale-ID rule (DESIGN §3), which would
  have needed ChatGPT to pass box IDs.
- Seeds: stored as **plain text**; **no size limit** (output batches seeds if they don't fit one
  pass). Pasting now; later, links and files (.txt/.md/.docx/text PDFs) via
  extract → show → confirm. Scanned PDFs are refused (image-to-text is out of scope; the user
  can convert elsewhere and paste). Code-style seeds from repos are out of scope.
- Profiles box gets **Clear seeds** (two clicks, permanent; tunes stay).

## 2026-11-01 — Build step 2: current profile and seeding

- Every MO box has a profile dropdown; picking one makes it current (HUMAN USER ·
  `current_profile_set`) and switches that box. New boxes lock in the current profile; open
  boxes keep theirs. Deleting the current profile clears it.
- `@MO seed`: ChatGPT only opens the box; the human user pastes and saves. Stored as plain text
  (only line breaks unified), no size limit. The `seed_added` event holds the id and word count,
  never the text.
- Profiles box: current profile marked; **Clear seeds** (two clicks; tunes stay). Delete and Clear
  share one confirmation mechanism (one-time code tied to box, action, and profile).

## 2026-11-01 — Seed management and seeds in the trace

- Human user test of seeding passed (a `shakespeare` profile with samples).
- The seed box lists the profile's seeds as a checklist; **Delete selected** deletes right away
  (no confirmation; the human user checked exactly what to delete). A box only deletes from its own
  profile. Event: HUMAN USER · `seeds_deleted`. Meant as the pattern tunes will reuse.
- `/trace` profile tabs show the profile's seeds with full text (local only), via
  `/trace/profiles/<name>`.

## 2026-11-01 — Output: explicit only (for now)

- The voice persists in MO's store and is applied only when the human user calls `@MO write`;
  ChatGPT's ordinary replies are untouched. Nothing outside ChatGPT can change them, and an
  "always on" voice would rely on ChatGPT following instructions (v0's limit).
- Later: **blending** the voice into everyday replies (e.g. plugin instructions asking ChatGPT to
  use `@MO write` whenever it writes), as an optional convenience that ChatGPT may skip visibly.
- Agreed for `@MO write`: MO diffs each version against the current cumulative one (and initial
  vs final) and shows the diffs in the trace; the human user sees only the final, in the MO box,
  shown only after the last pass. Identical text is refused; "no change" must be declared with a
  one-line reason (stored as a CHATGPT claim). No stylometric scores (Burrows' Delta etc.): the
  human user judges quality.
- Open: the pass prompt's wording steers ChatGPT; keep it minimal (no quality words like
  "improve"), fixed in one versioned file, shown per pass in the trace, owned by the human user.

## 2026-11-02 — Commands settled; Config box built

- Commands: plain `@MO` / `@MO menu` / `@MO help` → **Config box** (tabs: Profiles · Seeds · Help;
  `@MO profiles` and `@MO seed` open it on their tab). **`@MO` + anything → Output box** (next).
  "Write" was too narrow: output is anything ChatGPT can analyze, summarize, explain, or write.
- Output sources (files, text, links, repos) go through ChatGPT natively: the no-relay rule protects
  what MO stores as the user's and the user's evaluations, not material ChatGPT has to read anyway.
  Seeds still arrive only through the MO box.
- Each `@MO` message is one run and one Output box; without `@MO`, it's plain ChatGPT.
- Pass prompt v1 (the human user's wording calls): "reads like the EXAMPLES"; copying from seeds is
  not mentioned. Defaults: no current profile → the box asks; no seeds → 0 passes, labeled;
  seed batches ≈3,000 words; no "Rerun as" until a box can restart ChatGPT.

## 2026-11-02 — Build step B: Output

- `@MO` + anything: ChatGPT writes its full answer and calls `mo_output(initial, request)`; MO
  locks the run to the current profile, batches its seeds (oldest first, ≈3,000 words), and hands
  out pass 1 (prompt `pass-v1` + INITIAL + CURRENT + EXAMPLES). Each `mo_output_pass` is a new
  version (diffed against the current one) or a declared `no_change_reason`; identical text,
  out-of-order passes, and both/neither are refused. `mo_output_show` draws the Output box only
  after the last pass.
- ChatGPT's tools never take a profile; only `mo_output_show` and the config tools draw a box.
- Runs live in `profiles/<name>/runs/` (deleted with the profile). Events hold ids and numbers;
  the request is stored as a CHATGPT claim. `/trace` profile tabs show each run: initial → final
  and every pass as a word diff.

## 2026-11-02 — Spikes passed; voice per chat (approved)

- Spike 1: `_meta["openai/session"]`, attached by ChatGPT's app to every tool call, was one stable
  ID per chat (same across calls in a chat, different between chats). Not yet tested: stability
  across days. If it ever changes, the chat just asks for its voice again.
- Spike 2: a box can post a message into the chat (`window.openai.sendFollowUpMessage`), so a box
  can restart ChatGPT after the human user picks something.
- **AGENTS.md items 2 and 7 changed** (approved): three windows (Help, Config, Output); each chat
  has one current profile (its voice), set only by the human user in a box in that chat (Profiles
  tab, Output window, or the first-output prompt); used for output and for Config; nothing
  inherited. Results keep a read-only "in the voice of" label; changing the voice offers Rerun from
  the same initial. Replaces the global current profile (it was an assumption about intent).

## 2026-11-02 — Built: voice per chat, three windows, Rerun

- `mo_help`, `mo_config` (Profiles · Seeds), `mo_seed` open windows; the global current profile is
  gone. Each chat's voice is stored by a hash of its `openai/session`; deleting a profile clears
  it from every chat (they ask again). A window opened without a chat id can't set a voice.
- `@MO` + anything in a chat with no voice: the run waits; `mo_output_show` draws a voice picker;
  the human user's pick sets the chat's voice and readies the run; the window posts "continue MO run
  …" and ChatGPT calls `mo_output_continue`. A run belongs to its chat (other chats are refused).
- The Output window's result keeps a read-only "in the voice of" label; changing the chat's voice
  there offers **Rerun**: a new run from the same stored initial, in the new voice.

## 2026-11-02 — Availability over consistency (approved: AGENTS.md item 6)

- Observed: ChatGPT hit "Selected model is at capacity" after the last pass, so `mo_output_show`
  never ran and no window appeared, though the run was complete in MO. Measured: MO answers in
  ~1 ms locally and ~0.1–0.2 s through the tunnel; the rest of the wait is ChatGPT (a faster model
  fixed most of the menu delay).
- Decided: the Output window opens at `mo_output` and updates itself from MO (no `mo_output_show`
  step). It always shows the best version so far with "x% voice loaded" (seed words passed through
  ÷ all seed words in the run's batches). A run is stalled after 90 s without ChatGPT's next step;
  then "x% voice loaded. Continue?" (the user's click posts "continue MO run …"; MO never retries).
  At 100%: "Not satisfied? Tune voice profile" (greyed until tune exists). Voiceless runs expire
  after 24 h.

## 2026-11-02 — Built: tune

- Entry: "Not satisfied? Tune voice profile" under a finished output, or `@MO tune` (this chat's last
  MO output, by MO's fixed rule; with none, the human user pastes text in the window).
- Steps: the human user says what part they didn't like → ChatGPT quotes it (MO refuses anything not
  word for word in the text) → "That's it" or "say more". Skip: MO takes the opening (first 3
  sentences). Each round ChatGPT writes A/B/C (distinct, locked); the human user picks one and may
  comment, or picks none and must comment; a pick without confirming becomes the next round's base
  (C → C1, C2, C3 …) until confirmed. The whole decision tree is stored; confirming seals it into the
  voice and shows the text with the tuned part swapped in. Unconfirmed tunes expire after 24 h.
- Output: seeds first, then tunes ranked by rounds (most first) in batches of **1, 3, 10, 30**, then
  100s (the human user's "rule of 3s"); each tune contributes its final, notes, and rejected
  versions. Prompts `find-v1`, `tune-v1`, `tunes-v1` are drafts awaiting the human user's wording.
- Config has a Tunes tab (check and delete, no confirmation); the trace shows each tune's tree.

## 2026-11-02 — Tune, simplified after the human user's first test

- Observed: ChatGPT's own "automatic approval review" blocked tune steps posted by the window ("may
  modify tune or workflow state"), asked for authorization twice, and a second tune was opened.
- Changes: the whole tune UI is the MO window; ChatGPT only writes A/B/C. Start: a big **Begin
  Tuning** (tunes the sentences clicked, if any; otherwise MO picks the opening) plus an optional
  note ("is there a sentence that bothers you?"). Rounds: click **A**, **B**, or **C** and the next
  round varies it; **✓ Done** keeps the last pick; **None of these**; notes always optional (they only
  inform the next round). One tune per chat: reopening resumes it; **Start over** discards it.
- For the approval reviewer: "what's next?" calls (`mo_tune_work`, `mo_output_continue`) are truly
  read-only and annotated `readOnlyHint`; drafting calls are `destructiveHint: false`,
  `openWorldHint: false`, and say "drafts only: nothing changes the user's profile until they confirm
  in the MO window". The stall clock now restarts on the user's Continue click. Posted messages read
  as the user's request ("I picked B in the MO tune window. Please continue MO tune …").

## 2026-11-02 — Network drops

- Observed: closing the laptop and switching Wi-Fi made the window show "Failed to fetch". MO and
  the quick tunnel survived (cloudflared reconnected with the same address); nothing was lost. But
  the window stopped polling after the error, so it stayed dead: an availability bug.
- Fixed: windows treat "can't reach MO" as temporary ("Reconnecting…") and retry every 4 s.
- Also: the window's URI now carries a hash of its code as well as MO's address, since ChatGPT
  caches windows by URI and a tunnel can keep its address across restarts.
- Fixed: a tune's round count (and its rank in output) counts answered rounds only.

## 2026-11-02 — Tune windows follow the chat

- Observed: picture-in-picture didn't happen on ChatGPT web, and each round's posted line plus
  ChatGPT's reply still pushed the tune window up out of view.
- Changed: `mo_tune_variants` draws each round's window itself, at the bottom of the chat, already
  filled in (a snapshot in hidden `_meta`, so no "waiting" flash). The tune records its newest
  window; older windows fold into a one-line stub ("Round 1 · picked C · continued below ↓"). Tune
  messages scroll the chat again (the live window is at the bottom); output windows still don't.

## 2026-11-02 — Centralized compute and storage; hosted on Fly.io

- Decided (the human user): centralize compute and storage. Estimates: MO's own infrastructure is
  ≈ $5–20/month at 1,000 daily users and ≈ $50–200/month at 100k users (10% daily), because ChatGPT
  does all generation on each user's plan; the sign-in provider may cost more than compute at scale.
- A user's whole MO state is tiny (≈ 0.5 MB after heavy testing): keep it as one portable set of
  files per user, so "store it in my Drive" or local-first remain options later. No database until
  many concurrent writers or more than one server.
- Hosting: Fly.io, one small machine (sleeps when idle) plus a 1 GB volume at /data holding the same
  JSON files as `~/.mo`. Fixed address `<app>.fly.dev`: the ChatGPT link is set once; `make deploy`
  ships changes. The secret link isn't printed in hosted logs (`make link`); the trace stays private
  via `make trace` (`fly proxy` to 127.0.0.1). Local `make run` stays for quick experiments.

## 2026-11-02 — Approved: users, sign-in, observability split (AGENTS.md items 2, 6, 7, 9, 12)

- 1 global → N users → N profiles, for data and trace. Sign-in (OAuth 2.1) with **WorkOS AuthKit**
  (free to 1M monthly users; MCP-ready), built and tested **before** anyone uses the hosted MO.
- Users see only their own seeds and tunes; the trace is a private operator tool (own full trace +
  anonymous metrics). Account deletion: two clicks, permanent, wipes the user's folder. 50 MB per user.
- Voice per chat is keyed by user + chat. Tune batches: 1, 3, 10, 30 (then 100s).
- Hosted MO starts clean (no local data copied up). Fly app `modus-operandi-v1` and its encrypted
  1 GB volume exist; nothing deployed yet.
- Next: a spike that ChatGPT's "Connect" completes with WorkOS against the hosted MO (the MCP spec is
  moving from dynamic client registration to client ID metadata documents), then user folders,
  per-call scoping, account deletion, the operator view, the 50 MB cap, then deploy.

## 2026-11-02 — Approved: hosted only, sign-in, trace per user (AGENTS.md items 2, 9, 10)

- **MO runs only hosted** (Fly.io), reached through ChatGPT. No local mode: the tunnel, `make run`,
  and the link secret go away; sign-in is the lock, so the MCP address can be public.
- **Anyone can sign up**, one click: Google, Microsoft, Apple (Apple needs a paid developer
  account; added last). No email codes; GitHub maybe later. MO stores only the WorkOS user ID.
- Data: **data → users → profiles**, each 1 → N. A user's folder holds everything they own.
- **Trace per user:** each user sees their own full trace (`@MO trace` window, or the trace page
  with the same sign-in). **Admins** (verified emails, kept in a Fly secret, not the repo) see every
  user's full data and trace, read-only. Users aren't notified. Banning: not in the MVP.
- Plan: [HOSTING.md](HOSTING.md). WorkOS client ID, API key, and admin list are Fly secrets.
- AGENTS.md Scope → Phase: finishing v1, hosted on Fly.io with WorkOS sign-in (approved).

## 2026-11-02 — Steps 1–2: sign-in works; full MO back, per user

- Sign-in spike: ChatGPT's Connect completed with WorkOS AuthKit (Dynamic Client Registration on);
  MO saw 401 → sign-in → 200. Mistake: the spike replaced the whole hosted MO with one tool, and the
  human user found every command gone. Next time say plainly what a deploy removes.
- Step 2 deployed: every MCP call needs a WorkOS token; MO's store is `/data/users/<id>/`;
  `mo_home()` takes the user from the token (always first) or, for a window's click, from
  `box-owners/<box>`; no user → refused, never a shared fallback. `mo_whoami` stays.
- Removed: the tunnel (`mo.dev`), `make run`/`link`/`trace`, the link secret. The trace page is off
  when hosted until step 3 (signed-in, per user).

## 2026-11-03 — Step 3: the trace, per user (built, waiting on the human user's test)

- `/trace`: signed out → a sign-in page; "Sign in" → WorkOS (same account as ChatGPT) →
  `/trace/callback` → MO trades the code for the user at WorkOS and sets its own signed cookie
  (user ID + expiry, 7 days, `MO_SESSION_SECRET`). Every data route reads only the signed-in user's
  folder; admins may add `?user=<id>`, and get `/trace/users` (IDs and counts) and a picker. Read-only.
- `@MO trace` opens a Trace window: this chat's last 15 events (ids and counts) and "Open full trace".
- Fixed on the way: the trace page called a missing `saveUrl()`, so tabs and filters errored.
- Not yet: alarms and OpenTelemetry (AGENTS.md item 9).
- `@MO debug` added as another name for `@MO trace` (AGENTS.md item 2, approved).

## 2026-11-03 — Window design: Swiss, quiet

- Direction (the human user's): Swiss / International Typographic Style; Rams, Jobs, Tufte; one Warhol
  signature in the branding, not everywhere. Personality: intelligent, precise, understated,
  authoritative, elegant. "Make the AI's complexity invisible until the user needs to inspect it.
  Then make that complexity perfectly legible."
- Applied to the MO windows: one grotesque (Helvetica Neue), small uppercase set labels, hairline
  rules, square controls, ink on paper. Red only in MO's mark (the signature: a small red square
  before the window name) and in warnings and confirmations. Secondary and destructive actions are
  quiet text until pointed at. The output shows the result and one line of facts; "How MO got here"
  folds open to a table (voice, passes, voice loaded, % changed, Open full trace).
- Not yet restyled: the trace page and its sign-in page.
- **Rolled back the same day:** the human user found the restyled windows worse. The windows are back
  to their earlier look (the trace window and `@MO debug` stay). Next time: show screenshots and get a
  yes before deploying a visual change.
- Fixed: after a deploy ChatGPT asked for the old window address (`ui://mo/box-38ebf9b1.html`) and got "Unknown resource", so `@MO tune` showed no window. MO now answers any `ui://mo/box-*.html` with the current window.

## 2026-11-03 — Stuck tunes, Retry, and only the newest window is interactive

- Observed: after Begin Tuning, the window's "continue MO tune …" message never reached the chat, so
  ChatGPT never wrote A/B/C and the window said "Writing A, B, C…" with no way forward. MO couldn't
  see why: posting into the chat happens between the window and ChatGPT only.
- Now: the window reports each message to MO (`followup_sent` / `followup_failed`, actor MO,
  reported_by window). If ChatGPT hasn't asked MO for the work 20 s after the user's click (90 s once
  it has started), the window shows "ChatGPT didn't pick this up" with **Retry** (the user's click;
  MO still never retries on its own) and the exact message to copy into the chat.
- Approved: **only the chat's newest MO window is interactive.** MO records each chat's newest
  window; clicks from older ones are refused (409) and logged; reading still works, and older
  windows grey out with "A newer MO window is open below."
- Tune rounds now show what's being varied above A/B/C: "The part you're tuning", then "Your pick
  from round N (X)".
