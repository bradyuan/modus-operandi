from mo import checks


def flag_types(result):
    return [f["type"] for f in result["flags"]]


def test_clean_draft_passes():
    result = checks.run_checks("I fixed the outage in two hours and wrote up what broke.")
    assert result["status"] == "passed"
    assert result["fix"] == []


def test_ai_tells_are_flagged_with_fixes():
    result = checks.run_checks("I'm excited to leverage my skills in a fast-paced environment.")
    assert result["status"] == "failed_checks"
    details = {f["detail"] for f in result["flags"] if f["type"] == "ai_tell"}
    assert {"i'm excited to", "leverage", "fast-paced environment"} <= details
    assert all(fix for fix in result["fix"])


def test_ai_tells_match_whole_words_only():
    assert checks.check_ai_tells("The leverage ratio") != []
    assert checks.check_ai_tells("Elevated trains") == []


def test_copied_phrases_from_source_are_flagged():
    source = "You will collaborate with cross-functional stakeholders to drive alignment across teams."
    draft = "At my last job I would collaborate with cross-functional stakeholders every week."
    result = checks.run_checks(draft, source_text=source)
    copied = [f["detail"] for f in result["flags"] if f["type"] == "copied_phrase"]
    assert copied and "cross" in copied[0]


def test_copied_phrases_allow_keywords_and_own_words():
    source = "Experience with incident response and on call rotation for production systems required."
    draft = "I led incident response and on call rotation for production systems at Acme."
    own = "I led incident response and on call rotation for production systems at Acme."
    assert checks.check_copied_phrases(draft, source, [], own) == []
    # Without the user's own notes, the same run is flagged.
    assert checks.check_copied_phrases(draft, source, [], "") != []


def test_unsupported_numbers():
    flags = checks.check_unsupported_numbers("Grew revenue 40% across 12 markets.", "revenue grew 40 percent")
    assert [f["detail"] for f in flags] == ["12"]


def test_checkable_rules_only_when_strong_enough():
    strong = {"rule": "Never say 'utilize'.", "hits": 6, "misses": 0, "check": {"type": "banned_phrase", "value": "utilize"}}
    weak = {"rule": "Never say 'synergize'.", "hits": 0, "misses": 3, "check": {"type": "banned_phrase", "value": "synergize"}}
    flags = checks.check_rules("We utilize tools to synergize.", [strong, weak])
    assert [f["detail"] for f in flags] == [strong["rule"]]


def test_max_words_and_max_count_rules():
    rules = [
        {"rule": "Keep it under 5 words.", "hits": 5, "check": {"type": "max_words", "value": 5}},
        {"rule": "At most one em dash.", "hits": 5, "check": {"type": "max_count", "pattern": "—", "value": 1}},
    ]
    flags = checks.check_rules("One — two — three four five six", rules)
    assert len(flags) == 2


def test_missing_keywords_warn_but_do_not_fail():
    result = checks.run_checks("I like Python.", keywords=["Kubernetes"])
    assert flag_types(result) == ["keyword_missing"]
    assert result["status"] == "passed"


def test_seed_retention():
    seed = "I broke prod once and it taught me more than any course"
    assert checks.seed_retention(seed, seed + ". Since then I write tests first.") == 1.0
    assert checks.seed_retention(seed, "Something entirely different.") < 0.2


def ex(text, name="s"):
    from mo.store import Exemplar
    return Exemplar("essay", name, text, 0.0)


LONG_SAMPLE = ex(
    "When I started building the scheduler I assumed the hard part would be the algorithm, but the hard part "
    "turned out to be convincing everyone that the old cron jobs were quietly failing every other night. "
    "I believe the fix mattered less than the dashboard that finally made the failures impossible to ignore, "
    "and once people could see the gaps they stopped arguing and started helping me close them one by one."
)


def test_list_numbers_and_headings_are_not_claims():
    draft = "### 1. Why us?\nBecause.\n\n2. Next question\nI grew users 40% in 3 months.\nQ4) Last"
    assert [f["detail"] for f in checks.check_unsupported_numbers(draft, "40% growth")] == ["3"]


def test_numbers_in_the_authors_samples_are_supported():
    result = checks.run_checks("Retention went from 6% to 14%.", exemplars=[ex("Retention was 6% and then 14%.")])
    assert "unsupported_fact" not in flag_types(result)


def test_ai_tells_in_headings_are_ignored():
    assert checks.run_checks("### How do you thrive in a fast-paced environment?\nI ship small.")["status"] == "passed"


def test_hedges_the_author_never_uses_are_flagged_one_by_one():
    draft = "I think this works. I think it scales. I believe in it."
    details = [f["detail"] for f in checks.check_voice_habits(draft, [LONG_SAMPLE])]
    assert details == ["hedge:I think"]          # "I believe" appears in the sample, so it's fine


def test_repeated_contrasts_are_flagged_relative_to_the_author():
    draft = ("It is less about speed and more about direction. It is not just code but care. "
             "I chose tests rather than hope. I fix causes rather than symptoms.")
    assert "contrast" in [f["detail"] for f in checks.check_voice_habits(draft, [LONG_SAMPLE])]


def test_voice_habits_need_samples():
    assert checks.check_voice_habits("I think so. I think not.", []) == []
