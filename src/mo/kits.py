"""Build the kits MO hands to the host AI (see docs/DESIGN.md §4.3, §7)."""

from __future__ import annotations

from typing import Any

from mo import style
from mo.store import Exemplar, Profile, validate_register

ALWAYS, PREFER = 0.8, 0.5
RULE_TOKEN_BUDGET = 1500
MAX_EXEMPLARS = 3
MAX_KEYWORDS = 5
SEED_OFFER = "Want it more like you? Give me one sentence on your take."


def weight(hits: int, misses: int) -> float:
    """Rule weight from evidence (Beta(1,1) posterior mean): 1/1 -> 0.67, 12/13 -> 0.87."""
    return (hits + 1) / (hits + misses + 2)


def rule_weight(rule: dict[str, Any]) -> float:
    return weight(int(rule.get("hits", 0)), int(rule.get("misses", 0)))


def strength(w: float) -> str | None:
    """How strongly a rule is sent to the host: 'always', 'prefer', or not at all."""
    return "always" if w >= ALWAYS else "prefer" if w >= PREFER else None

WRITING_STEPS = [
    "Treat SEED as the start of the author's own document and continue it in the same voice. "
    "Keep the author's words; add facts and connecting text around them.",
    "Match the voice of EXEMPLARS (rhythm, word choice, structure). Never copy their sentences.",
    "Use facts only from FACTS and SEED. Never add numbers, names, or claims that aren't there.",
    "Treat REQUIREMENTS as a checklist to cover. Never reuse their wording, except the approved KEYWORDS.",
    "Apply RULES: 'always' rules strictly, 'prefer' rules where they fit. Apply MODIFIERS to this piece only.",
    "Before showing the draft, call mo_check with it. Fix only the flagged parts, at most 2 tries, "
    "and keep the version with the fewest flags.",
    "If the user dislikes the draft or part of it, call mo_tune(action='start', mode='draft', ...). "
    "When the user edits the draft themselves, call mo_record with kind='edit'.",
]


READING_STEPS = [
    "Read the source yourself and gather broadly: claims, how it works, examples, prerequisites, "
    "background, caveats, and exact quotes with where they appear.",
    "Explain it using RULES: 'always' rules strictly, 'prefer' rules where they fit. Apply MODIFIERS to "
    "this explanation only.",
    "Stay faithful: no claims, numbers, or quotes that aren't in the source. Say what the source leaves out.",
    "If it doesn't click, or the user asks for a different explanation, call mo_tune(action='start', "
    "mode='draft', task='reading', target=<the part that didn't land>, source=<the source>).",
    "When the user says what they liked or didn't, call mo_record(kind='rating', task='reading').",
]
def reading_kit(profile: Profile, source: str | None = None, question: str | None = None,
                modifiers: list[str] | None = None) -> dict[str, Any]:
    rules = select_rules(profile.rules(), "reading", "other")
    notes = []
    if not rules:
        notes.append("New reader profile: explain plainly with the main point first, then offer @MO tune "
                     "(mode='diagnostic', task='reading') to learn what clicks for them.")
    return {"profile": profile.name, "task": "reading", "source": source, "question": question,
            "rules": rules, "modifiers": modifiers or [], "steps": READING_STEPS, "notes": notes}


def select_rules(rules: list[dict[str, Any]], task: str, register: str) -> list[dict[str, Any]]:
    selected = []
    for rule in rules:
        if task not in rule.get("scope", [task]):
            continue
        registers = rule.get("registers")
        if registers and register not in registers:
            continue
        w = rule_weight(rule)
        level = strength(w)
        if level is None:
            continue
        selected.append({"rule": rule["rule"], "why": rule.get("why"), "strength": level, "weight": round(w, 2)})
    selected.sort(key=lambda r: r["weight"], reverse=True)

    budget, kept = RULE_TOKEN_BUDGET, []
    for r in selected:
        cost = (len(r["rule"]) + len(r["why"] or "")) // 4 + 8
        if cost > budget:
            break
        budget -= cost
        kept.append(r)
    return kept


def select_exemplars(profile: Profile, register: str) -> tuple[list[Exemplar], str | None]:
    """Pick the exemplars most representative of the user's style for this register.

    Returns the exemplars and the register they came from (None if there are none).
    """
    pool = profile.exemplars(register)
    source = register
    if not pool:
        # Borrow from the register with the most samples.
        others = sorted(profile.registers_with_exemplars(), key=lambda r: len(profile.exemplars(r)), reverse=True)
        if not others:
            return [], None
        source = others[0]
        pool = profile.exemplars(source)

    vectors = [style.style_vector(e.text) for e in pool]
    center = style.centroid(vectors)
    ranked = sorted(zip(pool, vectors), key=lambda pv: (style.distance(pv[1], center), -pv[0].modified))
    return [e for e, _ in ranked[:MAX_EXEMPLARS]], source


def writing_kit(
    profile: Profile,
    register: str,
    seed: str | None = None,
    facts: str | None = None,
    requirements: str | None = None,
    keywords: list[str] | None = None,
    modifiers: list[str] | None = None,
) -> dict[str, Any]:
    validate_register(register)
    rules = select_rules(profile.rules(), "writing", register)
    exemplars, exemplar_register = select_exemplars(profile, register)
    keywords = keywords or []

    notes = []
    if exemplar_register and exemplar_register != register:
        notes.append(f"No {register} samples yet; exemplars borrowed from {exemplar_register}. Tell the user.")
    if len(keywords) > MAX_KEYWORDS:
        notes.append(f"Only the first {MAX_KEYWORDS} keywords were approved; more makes it sound like the source.")
        keywords = keywords[:MAX_KEYWORDS]

    if not seed:
        notes.append(
            "No seed was passed. If the user wrote ANY of their own words for this piece (notes, bullets, a rough "
            "line), call mo_write again with those words verbatim as `seed` before drafting."
        )
    if seed:
        seed_source = "user"
    elif exemplars:
        seed_source = "exemplars"
        notes.append(f"No seed given: continue the author's voice from EXEMPLARS, then offer: '{SEED_OFFER}'")
    else:
        seed_source = "none"
        notes.append(
            "New user with no profile: write plainly and avoid AI tells, then offer a 2-minute calibration "
            "(a few writing samples)."
        )

    return {
        "profile": profile.name,
        "task": "writing",
        "register": register,
        "seed": seed,
        "seed_source": seed_source,
        "exemplars": [{"name": e.name, "register": e.register, "text": e.text} for e in exemplars],
        "rules": rules,
        "facts": facts,
        "requirements": requirements,
        "keywords": keywords,
        "modifiers": modifiers or [],
        "steps": WRITING_STEPS,
        "notes": notes,
    }
