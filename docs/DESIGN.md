# Modus Operandi — Product Design

Status: Draft · Last updated: 2026-10-30

> Everything you read makes sense to you. Everything you write sounds like you.

`AGENTS.md` is the source of truth; this document fills in the details and must not contradict it.

---

## 1. The idea

MO keeps a **persistent profile of you** and applies it in two directions:

| Direction | Input → Output | Example |
|---|---|---|
| **Reading** (world → you) | Any source → an explanation built on what you already know | A paper on clearinghouses explained in terms of servers and APIs |
| **Writing** (you → world) | A rough idea + data → finished prose in your voice | Bullet notes + a spreadsheet → three paragraphs that sound like you wrote them |

**Value promise:** reading and synthesizing a topic, 2 hours → ~10 minutes. Writing it up, 2 hours → ~10 minutes.

**MO is a harness, not a generator.** MO keeps and supplies state (your profile, cases, rules), tells the host AI (ChatGPT, Claude) how to use it, and checks the results with plain code. **The host AI does all the reading and writing.** MO makes no LLM calls, so it has no API bill and no model to choose.

```
 Host AI (ChatGPT / Claude)                 MO (harness)
 ─────────────────────────                  ─────────────
 reads, writes, makes variations   ◄──────  kit: your rules + exemplars + workflow steps
 sends drafts for checking         ──────►  mo_check: plain-code lint + voice checks
 relays your picks and edits       ──────►  mo_record: logs cases
 proposes rules from cases         ◄──────► mo_calibrate: weights, yes/no approvals, storage
```

## 2. The feedback loop

```
  result ──► "@MO tune" ──► host makes 3 variations (as MO specifies) ──► you pick one
      ▲                                                                       │
      │                                                                       ▼
  next results ◄── rules (weighted) ◄── canonical cases ◄── individual cases (logged by MO)
  use the rules     (approved via yes/no)    (compacted)
```

1. **Reject:** `@MO tune`, or "I don't like this" (optionally, why).
2. **Variations:** MO's kit tells the host to make **3 variations that each differ in one way** (e.g. mechanism-first / analogy-first / example-first). Because MO chose the differences, your pick shows *why* without you having to type it.
3. **Pick:** MO logs it as an individual case: the rejected result, the chosen variation, and the ones passed over.
   - **None fit?** MO asks for 3 more, changing something different (e.g. depth or format instead of the opening). Every rejected variation is logged. After two rejected rounds, the host briefly asks what's off.
4. **Compact:** individual cases are folded into canonical cases (rules) at every opportunity (§4).
5. **Apply:** the next kits carry the updated rules. Rinse and repeat.

**Immediate vs. persistent effect:**
- Your pick affects the **current piece** immediately.
- It changes the **persistent profile** only after you say yes (§3).

## 3. Two modes

| | **Calibrate** | **Use** |
|---|---|---|
| Purpose | Turn collected cases into approved rule changes | Get work done |
| Profile | Read/write, with your approval | **Read-only** |
| Feedback | Applied | Logged as individual cases |
| Drift risk | Controlled | None |

- **Users never need the word "Calibrate."** It shows up as occasional yes/no questions: *"You keep picking punchier openings. Make that a rule?"*
- **Initial calibration** is a short warm-up: a few same-content A/B pairs plus optional writing samples. Most learning comes from the loop in §2.
- **Questions are prompted** when enough cases pile up, never in the middle of a task.
- **Approval friction** *(default; open for confirmation)*:
  - Weight changes to existing rules are approved together in one summary.
  - New rules and rule splits are reviewed one at a time.

  > Rule "mechanism first": 0.71 → 0.84 (+5 cases) · New candidate: "skip historical background" (3 cases) · **Approve all / review each**

## 4. The weighting funnel

**Compaction rule:** always try to fold individual cases into existing canonical cases, so data and context don't explode.

```
Individual cases  →  Candidates  →  Rules (canonical cases)
  raw data            pattern seen     promoted after ~5 cases;
  logged in Use       2–4 times;       weighted 0–1;
                      not applied      sent in kits
```

### 4.1 Rules

- **Reinforce before creating.** A new case first strengthens or weakens a matching rule. A new candidate is created only when nothing matches.
- **Weights come from evidence:** `weight = (hits + 1) / (hits + misses + 2)`, so 1/1 → 0.67 and 12/13 → 0.87. The weight reflects how much evidence there is, not just the ratio. MO computes this in plain code.
- **Weights go both ways.** Counter-evidence lowers a weight, and old evidence slowly counts for less (decay), because preferences change.
- **Mixed evidence → split.** A rule with ~50/50 evidence is usually two rules in different contexts, e.g. "short for email" and "long for essays."
- **Specificity check.** Rules too vague to act on ("be clear") are rejected.
- **Checkable vs. fuzzy.** Each rule is tagged:
  - **Checkable** rules can be tested by code ("no em dashes," "under 250 words," "never 'leverage'"). `mo_check` enforces them with a pattern or count, which is real enforcement.
  - **Fuzzy** rules ("lead with a scene") are sent in the kit as guidance; you catch misses through picks and edits.
  - The more preferences become checkable rules, the more MO enforces rather than suggests.

### 4.2 Matching

- During calibration, **MO hands the host the new cases and the existing rules**. The host proposes which rule each case belongs to, or proposes a new candidate. MO stores the result and recomputes the weights.
- You get a quick check: *"I counted these 4 as 'mechanism first.' Right?"*

### 4.3 What goes into a kit

**Selection is deterministic, not semantic search.** The lookup key is **(profile, task, register)**:

| Step | How | Who decides |
|---|---|---|
| Profile | Named explicitly ("as journal"), else the last-used one, else the default | MO |
| Task | `read` / `write` / `tune` | The host, by picking the tool |
| Register | A `register` input with a fixed list of values (email, essay, cover letter, article…). The widget shows it so you can correct it. | The host proposes, MO validates |
| Rules | Every rule for that task and register with weight ≥ 0.5, ranked by weight. The profile is compact, so it almost always fits whole. | MO |
| Exemplars | Filter by register, then the 1–3 **most representative of your style** (closest to your stylometric average) and highest-rated | MO |
| Influences | Accepted ones for this register only | MO |
| Modifiers | From the request | The host |

**No vector search or RAG.** It isn't needed, since the profile fits whole, and topic-similar exemplars could even hurt: the host might borrow their content and phrasing. Every choice is explainable: *"you got these 2 exemplars because they're your highest-rated essays and the closest to your average style."*

**Kits only ever contain rules and exemplars, never raw cases.** Weights are turned into instruction strength:

| Weight | In the kit |
|---|---|
| ≥ 0.8 | "Always …" |
| 0.5–0.8 | "Prefer …" |
| < 0.5 or candidate | Not sent; tracked only |

Rules are ranked by weight to fill a ~1–2k token budget, plus 1–3 relevant exemplars.

**Re-anchoring:** every MO call puts the kit **fresh at the end of the host's context**, where it carries the most weight. This counters instructions fading over a long chat. It's the harness's main defense against drift, together with `mo_check`.

### 4.4 Storage

- Raw cases are **archived**, never sent in kits. They're tiny: thousands of cases fit in a few MB.
- The archive is the source of truth. If the weighting method changes, rules can be **rebuilt by replaying the log**, with no recalibration needed.

### 4.5 Data shape

```yaml
rules:
  - id: R3
    rule: "Show the mechanism before the abstraction."
    why: "Abstractions don't stick until I've seen it work."
    scope: [reading]
    hits: 12
    misses: 1
    weight: 0.87        # derived, never set by hand
    check: null         # fuzzy; a checkable rule has e.g. {type: banned_phrase, value: "leverage"}
    cases: [c014, c022, c031]
candidates:
  - id: K7
    pattern: "Skip historical background unless asked."
    cases: [c040, c041, c045]
cases:                  # archive; source of truth
  - id: c014
    type: variations    # variations | pair | edit | rating
    rejected: a1
    chosen: a3
    passed_over: [a2]
    varied: "mechanism-first vs analogy-first vs example-first"
    note: "A lost me at the intro"   # optional
```

## 5. Profile vs. modifiers

- **Profile:** who you are (how you understand, how you sound). Stable, and changed only by approved yes/no questions.
- **Modifiers:** what this particular piece needs: persuasive, gentle, flirty, commanding, succinct. Chosen per request, and **never** written to the profile, so one flirty email doesn't leak into your permanent voice.

## 6. Reading flow

```
 you: "@MO explain this paper / repo"
 ① Host calls mo_read → MO returns the kit: your reading rules + the FIXED gathering schema
 ② Host reads the source and fills the schema broadly:
    claims · mechanism · examples · prerequisites · background ·
    caveats/limitations · quotes with locations
 ③ Host shapes the explanation using your rules (cut, reorder, choose analogies, set depth)
 ④ @MO tune → 3 variations, shaped from the same gathered material
```

- **Gather broadly, then cut.** Dropping what you don't need is reliable. Adding what was never gathered isn't.
- **Variations are cheap.** They come from the same gathered material, with no re-reading.
- **Bounded:** generous limits per field, not "everything." For more depth, a targeted follow-up ("go deeper on section 3").
- **Caveats are never removed entirely.** At minimum they shrink to a one-line *"what this leaves out."*

## 7. Writing flow: voice first

The piece is built **from your voice outward**, not from the facts with your voice painted on top.

```
 you: "@MO write my cover letter" (+ notes, resume, job description)
 ① Host calls mo_write → MO returns the kit:
      your voice rules for this register + 1–3 exemplars + your seed (if any) + steps
 ② Host writes from the seed outward, looking facts up in the fact sheet
 ③ Host calls mo_check(draft) → MO returns flags
      (copied phrases, AI tells, seed retention, voice distance, unsupported facts, coverage)
 ④ Host fixes the flagged parts (up to 2 tries), then shows the draft via mo_present,
      which re-checks it and displays it with its check status (§11.6)
 ⑤ Widget: @MO tune → 3 variations · edit inline → mo_record → cases → funnel
```

| Source | Role |
|---|---|
| Your seed + exemplars | **The voice to extend** |
| Resume / notes | Facts to look up |
| Job description / assignment | A checklist of requirements + ≤5 approved keywords; **never imitated** |
| Influences (§8) | Techniques to borrow, if you choose them |

- **No seed?** ("hey can you write an essay about monkeys @MO")
  - **Result first, never blocked.** The kit uses your **stored exemplars for that register** as the seed.
  - The widget then **offers** (never requires): *"Want it more like you? Give me one sentence on your take."* Your answer becomes the seed for the next round.
  - **No exemplars for that register?** MO borrows from your nearest register and says so.
  - **Brand-new user with no profile?** A plain, low-AI-tell kit plus an offer of a 2-minute calibration.
- **Commands are intents, not syntax.** "@MO" can appear anywhere in a casual sentence. The host routes it by matching tool descriptions (§11).
- **Minimal damage.** The kit tells the host to keep your words and add facts around them. `mo_check` measures how much of your wording survived.
- **Continuation framing.** The kit frames the task as "continue this author's document," not "write a cover letter," which avoids the assistant/corporate default.
- **Long pieces:** outline first (thesis + points), then section by section, with the kit re-supplied for each section.
- **One possible technique: write generously, then cut.** Deleting can't introduce generic wording. This is an implementation choice; use it if testing shows it helps.

## 8. Voice evolution and influences

Your voice isn't frozen. It **evolves, but only through suggestions you accept.**

```
 Base voice (your samples) ── the anchor; you stay recognizable
      +
 Influences (writers you admire) ── techniques to borrow, each with a weight
      e.g. Gay Talese, "Frank Sinatra Has a Cold":
           open with a scene, not a thesis · close observed detail ·
           build the subject through the people around it
```

- **Adding an influence:** `@MO tune` + "here's a perfect example." You can say what you like about it. The host names **specific techniques**, and MO stores them as candidates.
- **Evolving:** one of the 3 variations can apply an influence technique. If you pick it, the technique gains weight, and it can eventually become a rule ("open with a scene. From Talese.").
- **Techniques, not sentences.** `mo_check`'s copied-phrase lint also runs against influence texts. Borrowing a technique is craft; borrowing sentences is plagiarism.
- **Watch for pastiche.** Drifting toward Talese is still drift. An influence's weight is capped, and `mo_check` measures voice distance from your base voice.
- **Influences are scoped by register:** Talese for journalism, not for your emails.
- **Influence texts are private.** Copyrighted excerpts are never committed to this repository or shipped with MO.

## 9. Prior art to borrow from

| Method | Use in MO |
|---|---|
| Preference induction from user edits (e.g. CIPHER / PRELUDE research, 2024; verify details) | Inferring rules from edits and choices |
| Prompt optimization (DSPy, OPRO, TextGrad) | Later: tuning how kits are written, against the evaluation metric |
| Bradley-Terry + active learning | Choosing the most informative variations/pairs |
| Knowledge tracing (intelligent tutoring systems) | Modeling what you already know (reading) |
| Stylometry | Deterministic voice scoring in `mo_check` |
| Case-based reasoning | The individual → canonical case structure |
| Preference fine-tuning (DPO/RLHF) | **Not used:** MO is a harness and trains no models |

## 10. Evaluation

**You are the ground truth, and evals mostly come free from normal use:** every pick and edit is one.

**1. Human (you)**
- **⭐ North star: edit distance.** How much you change the draft before sending it. This should fall over time if MO is learning. It's measured automatically.
- **Pick prediction:** hold back some of your picks. Does the profile predict which variation you'd choose?
- **Blind test:** your real writing vs. MO vs. plain ChatGPT, shuffled. Which do you prefer, and can you tell which is yours?
- **Time saved:** time to understand or write, with and without MO.

**2. Deterministic (plain code, run on every output; the same code as `mo_check`)**

| Metric | Measures |
|---|---|
| AI-tell count | "leverage," "delve," reflexive lists of three… |
| Copied-phrase overlap | n-grams shared with the job description or influence texts (approved keywords excluded) |
| **Seed retention** | % of your seed's wording that survived |
| Stylometric distance | function words and sentence-length/punctuation patterns vs. your samples for this register. **Reported, never flagged** (see below) |
| Unsupported facts | numbers and names in the output that don't appear in the fact sheet |
| Coverage | job requirements and keywords addressed |

**Calibration on real authors (2026-10-31, `evals/calibrate_voice.py`, 16 public-domain books):**
- Overall voice distance separates authors only weakly on 200-word drafts: AUC 0.65 (0.5 is chance). Burrows' Delta and character n-grams did no better with a general word list. So it's a reported metric, never a flag.
- Sentence length varies too much within one author to flag; it's reported only.
- Habit checks compared with the author's own samples (hedges they never use, repeated "not X but Y" contrasts) wrongly flagged under 1% of authors' own passages, and caught both habits in a real ChatGPT run. These are the voice flags MO uses.

**3. LLM judge: later and optional, not in v0.1.** If you add one: pairwise comparisons, a different model from the writer, randomized order, and only trusted if it agrees with your picks about 80% of the time or more.

**The drift test (tests the core claim):** run a long conversation of about 30 turns containing job-description material. Measure the deterministic metrics at turns 1, 10, and 30, **with and without MO**. Without MO they should get worse; with re-anchoring and `mo_check` they should stay flat. This test decides whether the harness approach works.

**Golden set (regression):** a fixed set of tasks (3 job applications, 2 essays, 1 journal article, 3 papers to read), with your samples split into training and held-out sets. Rerun it after every design change.

**Where evals run:** an eval script in this repo calls model APIs directly to simulate the host. That's development tooling only; MO itself makes no LLM calls.

## 11. Front end and delivery

```
One MO MCP server
 ├─ mo_read(source?, modifiers)       → reading kit: rules + gathering schema + steps
 ├─ mo_write(seed?, facts, reqs, mods)→ writing kit: voice rules + exemplars + steps
 ├─ mo_tune(start | answer, ...)     → variation rounds; MO decides the next step (picked / none_fit / skipped)
 ├─ mo_check(draft, context)          → flags (plain code, no LLM)
 ├─ mo_present(draft, context)        → runs the checks, then shows the draft in the widget with its status
 ├─ mo_record(pick / edit)            → logs a case
 ├─ mo_calibrate()                    → yes/no rule suggestions; stores approved changes
 ├─ mo_profile(action, ...)           → list/create/use/show profiles; add_sample (one step; rejects text matching recent MO drafts);
 │                                      remove_sample
 └─ widget UI                         → buttons, selecting parts, editing inline
```

**How the host picks a tool:** each tool has a name, a plain-English description, and inputs. The host's AI matches what you typed to the descriptions, the same way `@Google Drive find my resume` maps to Drive's search tool. So "@MO I don't like this" reaches `mo_tune` without an exact command.

| Command users see | Tool | What happens |
|---|---|---|
| `@MO read <source>` | `mo_read` | Explanation shaped to you (§6) |
| `@MO write <notes/seed>` | `mo_write` | Voice-first draft (§7) |
| `@MO tune` | `mo_tune` | **The picker:** 3 variations for the last result or the selected part |
| `@MO tune` + "here's a perfect example" | `mo_tune` | Adds an example/influence; variations borrow its techniques (§8) |
| `@MO tune` + "give me variations" | `mo_tune` | More variations, changing something different each round |

- The host calls the helper tools (`mo_check`, `mo_record`, `mo_calibrate`) on its own, because each kit's steps tell it to.
- **Evolve vs. Calibrate:** `tune` affects the *current piece* and logs cases. Only an approved yes/no question changes the persistent profile. A "perfect example" applies to the current piece and is logged as a **candidate influence**.
- **Reading works the same way.** A "perfect example" can be an explanation that clicked for you once.
- **MCP prompts:** a server can also offer ready-made prompt templates that some hosts show as a menu or slash commands (e.g. `/mo-write`). Claude supports these; check whether ChatGPT does.
- **Why a widget:**
  - Buttons call MO's tools directly, with no host guessing.
  - Inline editing lets MO see your edits.
- **Edits made outside MO** (Word, Gmail) are lost unless you paste back "here's what I sent."
- Verify the current Apps SDK capabilities (widgets, `@` invocation, developer mode, file access) before building.

### 11.1 Where MO data is stored

**What's stored (per user):**

| Data | Format | Size | Sensitivity |
|---|---|---|---|
| Profile: rules, candidates, modifiers | `profile.yaml` | KBs | Medium |
| Case archive | `cases.jsonl` (append-only; the source of truth) | MBs | **High**: contains snippets of drafts |
| Exemplars (your writing, by register) | `exemplars/<register>/*.md` | KBs–MBs | **High** |
| Influence excerpts | `influences/*.md` | KBs | Copyrighted; private |
| Account | auth store | tiny | **Secret** |

**Not stored:** sources (job descriptions, papers, repos) and full drafts. Cases keep only the parts of text needed (the selected span and variations).

**Development (now):**
- Plain files in `~/.mo/`, **outside the repo**. `.mo/` is also gitignored in case it ever appears inside it.
- Human-readable on purpose: you can open your profile in an editor.

**Product (hosted):**
- A rented server (e.g. Supabase, Render, Fly.io) with a database: one row per user and profile, holding a **bundle with the same file layout**, encrypted.
- **Export** = download the bundle, the same files as in development. **Delete** = wipe the bundle and its keys.
- Honest limit: this is encryption at rest, not end-to-end. The server decrypts the data to build kits and run checks.

**Outside MO's control** (state this plainly to users):
- **The host and its model:** ChatGPT or Claude sees the kit (your rules and exemplars) and keeps the conversation according to the user's settings with that host.

**Retention:** the case archive grows forever by default. **Open:** a user-set retention window (e.g. keep 12 months, with the compacted rules kept forever)?

### 11.2 Multiple MOs (profiles) per user

**Register vs. profile:**

| | **Register** | **Profile** |
|---|---|---|
| Is | The same you in a different context | A deliberately different identity |
| Examples | email, essay, cover letter, journal article | "Personal" vs. "Pen name" vs. "Club newsletter" |
| Shares base voice and reading rules | Yes; rules can transfer, with scope tags | **No**; fully separate |

- **Default:** one profile with several registers. Most people only need this, and it's where the funnel learns fastest, because evidence is shared.
- **Separate profiles** are for identities that must not blend.
- **Isolation:** every case is tagged with its profile ID and only updates that profile. Influences are scoped to a profile too.
- **Choosing a profile:** `@MO write as <profile> …`. Otherwise the conversation's last-used profile, then the default. The widget always shows which profile is active.
- **Storage:** `~/.mo/profiles/<name>/` (`profile.yaml`, `cases.jsonl`, `exemplars/`, `influences/`), each exportable on its own.
- **Later:** shared profiles (a club's or team's voice) with permissions. Out of scope for now.

### 11.3 Hosts: chatgpt.com, claude.ai, and apps

One **hosted MCP server**, one MO account (OAuth sign-in), and **the same profiles everywhere**.

| Host | How it connects | UI | Invocation |
|---|---|---|---|
| ChatGPT (chatgpt.com, desktop, mobile) | ChatGPT app (Apps SDK) | MO widget | `@MO …` |
| Claude (claude.ai, desktop, mobile) | Custom connector (remote MCP) | Widget where supported, otherwise text | Enable the connector, then "use MO to…" |
| Claude Code / other MCP clients | Remote MCP | Text | Tool calls |

**Setup for a user:** add the MO app in the host's settings, sign in to MO once, then just type `@MO …`.

**Build path:**
1. Write the MCP server code in this repo (pushed to GitHub; GitHub only stores code).
2. Run it on your Mac and open a tunnel (e.g. ngrok) for a temporary public address.
3. Add that address in ChatGPT developer mode or as a Claude custom connector. Now `@MO` works for you.
4. Later: deploy to a rented server for a permanent address, and submit to OpenAI's app directory.

- **Picks and edits from every host go into the same funnel.**
- **Verify before building:** widget support in each host (the MCP Apps UI extension), plan requirements, and how each host shows invocation.

### 11.4 What MO doesn't control

MO controls **its own tools**, not ordinary host replies. No host lets a third-party app rewrite every response. That's a platform limit, not a bug to engineer around.

| Tier | How | Strength |
|---|---|---|
| **Harnessed** | `@MO read` / `write` / `tune`: kits, `mo_check`, picker | Strong, but only when invoked |
| **Ambient** | MO exports a short summary of your top rules to paste into ChatGPT Custom Instructions / Claude styles or project instructions | Weak and unchecked, but applies to every reply |

- **Positioning:** MO is what you call when it matters (a job application, an essay, a hard paper), not for "what's the capital of France."
- **Later:** a browser extension or MO's own app would give wider control, at much higher build cost.

### 11.5 Steering the host

| Lever | Strength | What it does |
|---|---|---|
| **Widget buttons** | ✅ Enforced | Call MO's tools directly, with no host model in the loop |
| **`mo_present`** | ✅ Enforced for MO's UI | The only way into the widget, and it runs the checks itself. Text the host pastes into chat instead is visibly not MO's output. |
| **Steps in each kit** | Usually followed | "Write from the seed. Treat the JD as a checklist. Call `mo_check` before showing. Make exactly these 3 variations. Call `mo_tune` for further changes." This is also the text-only fallback. |
| **Tool descriptions** | Discovery only | Tell the host when to call MO |

Not enforceable: free-typed revisions without `@MO` ("make it punchier"). Kit steps reduce these, but they can't be eliminated.

**Observability:** OpenTelemetry traces every tool call, recording whether the host called `mo_check`, whether flags got fixed, how routing went, and latency. Adherence for each host is a tracked metric, not a guess.

### 11.6 When output is wrong

**MO guarantees visibility, not correctness.** MO doesn't control the host's generation loop, so it can *request* retries but not force them. What it can guarantee: nothing appears in MO's UI unchecked, and failures are flagged, never hidden.

| Kind of wrong | Detected by | Response |
|---|---|---|
| Breaks a checkable rule (AI tells, copied phrases, over the word limit) | `mo_check` | Targeted retry with the specific flag as feedback |
| Invented facts (a number or name not in the fact sheet) | `mo_check` | Targeted retry, then flag it, never hide it |
| Misquoted source (reading) | `mo_check` verifies quotes word for word against the source text passed in the request | Drop or fix the quote, and mark the claim "unverified" |
| Host skipped the checks | `mo_present` checks anyway; telemetry | The draft shows ⚠️ with its flags |
| Wrong register or profile | Shown in the widget | One tap to correct it, and it's logged |
| Fuzzy wrong (doesn't sound like you, unclear) | **Only you** | `tune` or an edit |

**Retry rules:**
1. **Targeted, not regenerated.** Rewrite only the flagged part, and say exactly why.
2. **Bounded: 2 tries.** Then show the draft with its flags visible. No silent loops.
3. **Keep the best version.** Return the attempt with the fewest flags, never a worse one.
4. **Failures read like failures.** Structured results (`"status": "failed_checks", "fix": [...]`) are followed far more reliably than polite suggestions.
5. **User-triggered retry.** A **"Fix flags"** button in the widget sends a specific request into the conversation. Verify that the Apps SDK lets a widget send follow-up messages.
6. **System failures aren't preferences.** Failed checks are logged as system events, not as picks or edits, so they don't distort your rules.
7. **Repeated failures are a signal.** A check that keeps failing means the host can't follow the rule or the rule is too strict. Calibration can ask: *"This rule fails 40% of the time. Loosen it?"*

## 12. Known traps

- **The host writes in a long context.** MO has no quarantine; drift is countered by re-anchoring (§4.3) and caught by `mo_check`. The drift test (§10) must confirm this is enough.
- **The host may ignore kit steps.** It might skip `mo_check`, skip retries, or write its own variations. `mo_present` keeps checks unavoidable for anything in MO's UI, and telemetry measures the rest; test it early.
- **Simplifying can distort (reading).** Ground explanations in the source with quotes or links, and note what was left out.
- **Invented facts (writing).** `mo_check` flags numbers and names not in the fact sheet.
- **Wrong matches.** A case assigned to the wrong rule strengthens that rule without anyone noticing. Spot checks in calibration catch this.
- **Contaminated samples.** If writing samples were already AI-assisted, MO would be preserving AI voice.
- **Revisions outside MO.** "Make it punchier" typed to ChatGPT skips MO's kit and checks. Revisions should go through `tune` or the widget.
- **Pastiche.** Influences can pull the voice toward someone else's (§8).
- **Academic and workplace policies.** Some schools and employers restrict AI-assisted writing. That's the user's call, but MO shouldn't hide that it was used.

## 13. Open questions

- [ ] Hosting provider (Fly.io or Render)
- [ ] Exact fixed schemas: the reading gathering schema and the writing kit
- [ ] Confirm defaults: approval friction (§3), promotion at ~5 cases (§4), 3 variations with an optional why (§2), outline step for long pieces, ≤5 keywords, 2 fix tries (§7), cap on influence weight (§8)
- [ ] Decay rate for old evidence
- [ ] Case retention window (§11.1)

**Decided:** writing ships first (see `AGENTS.md`). Hosted product, local development (decision 006). Stack and visibility guarantee (decision 007).

---

*Reading is designed in detail in [READ.md](READ.md). Running as a Custom GPT: [GPT.md](GPT.md). The earlier coding-enforcement design is preserved in [ARCHITECTURE.md](ARCHITECTURE.md).*
