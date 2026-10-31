"""Build the kits MO hands to the host AI (see docs/DESIGN.md §4.3, §7)."""

from __future__ import annotations

from typing import Any

from mo import style
from mo.store import Exemplar, Profile, validate_register
from mo.weights import rule_weight, strength

RULE_TOKEN_BUDGET = 1500
MAX_EXEMPLARS = 3
MAX_KEYWORDS = 5
SEED_OFFER = "Want it more like you? Give me one sentence on your take."

WRITING_STEPS = [
    "Treat SEED as the start of the author's own document and continue it in the same voice. "
    "Keep the author's words; add facts and connecting text around them.",
    "Match the voice of EXEMPLARS (rhythm, word choice, structure). Never copy their sentences.",
    "Use facts only from FACTS and SEED. Never add numbers, names, or claims that aren't there.",
    "Treat REQUIREMENTS as a checklist to cover. Never reuse their wording, except the approved KEYWORDS.",
    "Apply RULES: 'always' rules strictly, 'prefer' rules where they fit. Apply MODIFIERS to this piece only.",
    "Before showing the draft, call mo_check with it. Fix only the flagged parts, at most 2 tries, "
    "and keep the version with the fewest flags.",
    "When the user picks between versions or edits the draft, call mo_record.",
]


DIAGNOSTIC_ROUNDS = 5
DIAGNOSTIC_AXES = {
    "reading": [
        ("opening", ["mechanism first (how it works)", "analogy first (from a field the user knows)",
                     "concrete example first"]),
        ("order", ["bottom line first", "build up to the point", "start from a question"]),
        ("depth", ["short (3–4 sentences)", "medium (a paragraph or two)", "deep (full detail)"]),
        ("format", ["plain prose", "bullet points", "a small diagram or table plus prose"]),
        ("background", ["no background", "one line of background", "full historical context"]),
    ],
    "writing": [
        ("tone", ["plain and direct", "vivid and concrete", "punchy and confident"]),
        ("rhythm", ["short sentences", "mixed short and long", "long, flowing sentences"]),
        ("opening", ["start with a story or scene", "start with the main point", "start with a question"]),
        ("formality", ["casual", "neutral", "formal"]),
        ("detail", ["lean: only what matters", "some supporting detail", "rich detail and specifics"]),
    ],
}


def diagnostic_kit(profile: Profile, kind: str, round_number: int = 1, source: str | None = None) -> dict[str, Any]:
    """One calibration round: the same content written 3 ways that differ along one axis."""
    axes = DIAGNOSTIC_AXES[kind]
    axis, options = axes[(round_number - 1) % len(axes)]
    labels = dict(zip("ABC", options))
    if kind == "reading":
        content = ("Read the source the user gave. Pick ONE short, meaty section and explain that same section "
                   "three times.")
    else:
        content = ("Use the user's notes on any topic (if there are none, ask for 2–3 lines of rough notes). "
                   "Write the same short paragraph three times, using only those notes.")
    steps = [
        content,
        f"Keep the content identical; vary ONLY the {axis}: " + "; ".join(f"{k} = {v}" for k, v in labels.items()) + ".",
        "Show them labeled A, B, C. Don't say which you prefer. Ask which one works best for the user, and why "
        "(optional).",
        f"Call mo_record with kind='variations', task='{kind}', and data={{'diagnostic': true, 'axis': '{axis}', "
        "'chosen': <letter>, 'passed_over': [<letters>], 'options': <the labels>, 'note': <their why, if any>}.",
        f"If none fit, record that with chosen=null. Then continue with round {round_number + 1} by calling "
        f"mo_profile(action='diagnostic', kind='{kind}', round={round_number + 1})"
        + ("." if round_number < DIAGNOSTIC_ROUNDS else ", or stop here; this is the last suggested round."),
    ]
    return {
        "profile": profile.name,
        "diagnostic": kind,
        "round": round_number,
        "of": DIAGNOSTIC_ROUNDS,
        "axis": axis,
        "variations": labels,
        "source": source,
        "steps": steps,
    }


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
