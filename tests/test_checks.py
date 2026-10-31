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
