# MO Read — Design

Status: Draft (proposal) · Last updated: 2026-10-31

> Read any blog post or paper. Keep asking for a different explanation until one clicks. Over time
> MO learns how to structure explanations so that *this* person understands them on the first try.

`AGENTS.md` (item 7) already fixes the shape: the host gathers the source broadly into a fixed
schema, then shapes it using the user's rules. This document fills in how the learning works.

---

## 1. What the research says (and the traps it rules out)

Citations are well-known papers, given from memory; verify before quoting them.

| Finding | What it means for MO |
|---|---|
| **"Learning styles" matching doesn't work.** Teaching to a "visual" or "verbal" learner doesn't improve learning (Pashler, McDaniel, Rohrer & Bjork, 2008). | **Don't label people** ("visual learner"). Learn which *specific explanation choices* work for this person, by measuring. |
| **Prior knowledge decides what helps.** Detail and guidance that help beginners slow experts down: the *expertise reversal effect* (Kalyuga et al., 2003). | The same person needs **different explanations for familiar and unfamiliar topics**. Preferences must be stored **per familiarity level**, not globally. |
| **Analogies work through structure mapping** from a domain you know well (Gentner, 1983). | Keep a **knowledge map** of the user's home domains (e.g. software, cooking, basketball) and draw analogies from them. |
| **Cognitive load and multimedia principles** (Sweller; Mayer): cut extraneous material, signal structure, break it into segments, introduce key terms first, and words plus diagrams beat words alone. | These are good defaults before anything is learned, and they define the dimensions MO varies (§2). |
| **Feeling that you understand isn't understanding.** Fluent explanations create an *illusion of explanatory depth* (Rozenblit & Keil, 2002). | "That clicked" measures **preference**. An optional **one-question check** measures **understanding**, and counts for more (§4). |
| **Retrieval and self-explanation build understanding** (Roediger & Karpicke, 2006; Chi et al., 1994). | The check doubles as learning: "Explain it back in one sentence" or one quick question. |
| **Knowledge tracing** models what a learner knows and updates it with evidence (Corbett & Anderson, 1994). | Track **concepts the user has confirmed understanding of**, so later explanations build on them instead of repeating them. |
| **Bandit algorithms** (e.g. Thompson sampling) balance trying new options against using what's known to work. | Choose **which dimension to vary next**, so tuning takes fewer rounds over time. |

## 2. The explanation space

An explanation is a set of choices along a few **dimensions**. `tune` varies one dimension per
round, which is what makes each pick informative. Current reading dimensions in `tune.py` are
marked ✓; the rest are proposed.

| Dimension | Options |
|---|---|
| ✓ **Entry point** | how it works (mechanism) · analogy · concrete example · definition |
| ✓ **Order** | bottom line first · build up to it · start from a question |
| ✓ **Depth** | short · medium · full detail |
| ✓ **Format** | prose · bullets · diagram + prose · table |
| ✓ **Background** | none · one line · full context |
| **Structure diagram** | flow (A → B → C) · layers (stack) · cause → effect chain · comparison table · concept map |
| **Analogy domain** | one of the user's home domains (from the knowledge map) |
| **Abstraction** | concrete numbers and cases · general principle · both |
| **Notation** | words only · light math or code · formal |
| **Prerequisites** | define them inline · link to a separate explainer · assume them |

The **structure diagram** dimension is the "sentence diagram" idea: the *shape* an idea is drawn
in. The host renders it as an ASCII diagram (works everywhere) or Mermaid (where supported).

## 3. The read loop

```
@MO read <blog / paper / repo> [question]
 ① mo_read → reading kit: your rules (per familiarity) + knowledge map + gathering schema + steps
 ② Host reads the source and fills the schema broadly:
    claims · mechanism · examples · prerequisites · background · caveats · quotes with locations
 ③ Host writes the explanation with your rules, then calls mo_check (task='reading'):
    quotes match the source word for word · terms you don't know are defined ·
    caveats present ("what this leaves out") · length budget
 ④ Doesn't click? → @MO tune (task='reading', target = the part that didn't land)
    picked → recorded · none_fit → same part, different dimension · skipped → move on
 ⑤ Clicked → optional check: one question, or "explain it back in a sentence"
 ⑥ Recorded: which dimension values worked, at what familiarity, and whether it was understood
```

All of ② and ③ is the host's work, guided by the kit; MO makes no LLM calls (AGENTS item 1).
The tune machinery from writing is reused unchanged.

## 4. How MO learns (cases → rules), deterministically

Tune picks are **structured**: each round records the dimension, the 3 options, and the outcome.
That means learning from them needs **no LLM**, only counting.

- **Evidence per (dimension, option, familiarity):**
  - **picked:** a hit for the chosen option and a miss for each option passed over
  - **none_fit:** a miss for all three
  - **skipped:** nothing
  - **understood (check passed):** counts double. Liked but **not understood** counts as a miss.
- **Weight** uses the existing formula `(hits + 1) / (hits + misses + 2)`.
- **Promotion:** when an option reaches weight ≥ 0.8 with at least 5 observations, MO asks one
  yes/no question: *"Analogies from software keep working for you on new topics. Make that a rule?"*
- **Example profile:**

```yaml
reading:
  unfamiliar:                    # expertise reversal: separate preferences per familiarity
    entry_point:  {analogy: 0.86, mechanism: 0.61, example: 0.44}
    structure:    {flow: 0.81, table: 0.52}
    depth:        {short: 0.78}
  familiar:
    entry_point:  {mechanism: 0.83}
    background:   {none: 0.90}
  home_domains: [software, basketball]           # for analogies
  known_concepts:                                # knowledge tracing, lightweight
    - {concept: "TCP handshake", confirmed: 2026-10-30, source: "blog: How TCP works"}
```

Writing benefits from the same aggregation: writing tune picks are structured the same way.

### Familiarity

- MO asks the host to classify the topic as **familiar or unfamiliar** for this user, using the
  known concepts and home domains in the kit.
- The widget shows it, and the user can correct it with one tap. The correction is logged.

## 5. Measuring whether it works

| Metric | Meaning |
|---|---|
| ⭐ **Rounds until it clicks** | The north star for reading. It should fall over time. |
| **Pick prediction** | On held-out tune rounds, does the profile predict which option the user picks? |
| **Check pass rate** | Understanding, not just preference |
| **First-try rate** | How often the first explanation lands without tuning |

## 6. Build order

1. **Deterministic aggregation** (§4) and the yes/no promotion questions. Shared with writing, and the biggest missing piece today.
2. **`mo_read`**: the reading kit, plus reading checks in `mo_check` (verbatim quotes, defined terms, caveats).
3. **Familiarity conditioning and the knowledge map.**
4. **The comprehension check.**
5. **Bandit choice of the next dimension**, so tuning converges in fewer rounds.

## 7. Open questions for the user

- [ ] **The comprehension check:** offered after every "it clicked", sometimes, or only on request?
- [ ] **Home domains:** ask during calibration ("what do you know really well?"), infer from picks, or both?
- [ ] **Diagrams:** is ASCII good enough, or should MO prefer Mermaid where the host renders it?
- [ ] **Scope of familiarity:** two levels (familiar / unfamiliar), or three (new / some / expert)?
- [ ] Approve changes to `AGENTS.md` for the knowledge map, familiarity conditioning, and the check
      (they extend core design items 5 and 7).
