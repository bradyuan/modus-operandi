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
