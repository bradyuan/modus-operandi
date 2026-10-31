from conftest import write_exemplar, write_rules

from mo import kits
from mo.kits import strength, weight


def test_weight_accounts_for_evidence():
    assert round(weight(1, 0), 2) == 0.67
    assert round(weight(12, 1), 2) == 0.87
    assert strength(weight(12, 1)) == "always"
    assert strength(weight(0, 0)) == "prefer"  # a hand-written rule with no evidence yet
    assert strength(weight(0, 2)) is None


def test_rules_ranked_filtered_and_phrased(profile):
    write_rules(profile, [
        {"rule": "Open with a scene.", "scope": ["writing"], "registers": ["article"], "hits": 5, "misses": 0},
        {"rule": "Short sentences.", "scope": ["writing"], "hits": 2, "misses": 1},
        {"rule": "Mechanism first.", "scope": ["reading"], "hits": 9, "misses": 0},
        {"rule": "Weak idea.", "scope": ["writing"], "hits": 0, "misses": 2},
    ])
    rules = kits.select_rules(profile.rules(), "writing", "article")
    assert [r["rule"] for r in rules] == ["Open with a scene.", "Short sentences."]
    assert [r["strength"] for r in rules] == ["always", "prefer"]
    # Register-scoped rules don't leak into other registers.
    assert [r["rule"] for r in kits.select_rules(profile.rules(), "writing", "email")] == ["Short sentences."]


def test_kit_uses_user_seed(profile):
    kit = kits.writing_kit(profile, "cover_letter", seed="I broke prod once.")
    assert kit["seed_source"] == "user"
    assert kit["steps"]


def test_kit_without_seed_falls_back_to_exemplars_and_offers(profile):
    write_exemplar(profile, "essay", "one", "I like short sentences. They hit hard.")
    kit = kits.writing_kit(profile, "essay")
    assert kit["seed_source"] == "exemplars"
    assert kit["exemplars"][0]["name"] == "one"
    assert any(kits.SEED_OFFER in n for n in kit["notes"])


def test_kit_borrows_from_nearest_register_and_says_so(profile):
    write_exemplar(profile, "email", "hi", "Hey, quick one. Can we move Friday?")
    kit = kits.writing_kit(profile, "cover_letter")
    assert kit["exemplars"][0]["register"] == "email"
    assert any("borrowed from email" in n for n in kit["notes"])


def test_new_user_gets_plain_kit(profile):
    kit = kits.writing_kit(profile, "essay")
    assert kit["seed_source"] == "none"
    assert kit["exemplars"] == []


def test_keywords_capped(profile):
    kit = kits.writing_kit(profile, "cover_letter", keywords=list("abcdefg"))
    assert kit["keywords"] == list("abcde")


def test_exemplars_pick_most_representative(profile):
    typical = "I write short lines. I keep it plain. I say what I mean."
    write_exemplar(profile, "essay", "a", typical)
    write_exemplar(profile, "essay", "b", typical.replace("plain", "simple"))
    write_exemplar(profile, "essay", "c", typical.replace("mean", "think"))
    write_exemplar(profile, "essay", "odd", "Whereas, notwithstanding the aforementioned considerations, "
                   "it may be argued, perhaps, that the matter, in its entirety, remains unresolved, and so forth?")
    write_exemplar(profile, "essay", "e", typical.replace("short", "brief"))
    chosen, _ = kits.select_exemplars(profile, "essay")
    assert "odd" not in [e.name for e in chosen]
