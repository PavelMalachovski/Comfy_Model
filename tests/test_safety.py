from typing import get_args

import pytest

from comfy_model.safety import TIER_RULES, Tier, check_prompt, normalize

TIERS = ("instagram", "social", "fanvue")


@pytest.mark.parametrize("text", ["a teen girl", "School-Girl outfit", "TEENAGER", "18yo woman",
    "17 year old", "loli style", "young girl", "high-school uniform", "underage"])
def test_age_terms_banned_everywhere(text):
    for tier in TIERS:
        assert check_prompt(text, tier)


@pytest.mark.parametrize("text", ["nude on bed", "Topless", "naked_", "nipples", "explicit", "NSFW"])
def test_nudity_banned_all_tiers_v1(text):
    for tier in TIERS:
        assert check_prompt(text, tier)


@pytest.mark.parametrize("text", ["black lingerie", "lace bra", "panties", "underwear"])
def test_lingerie_banned_only_on_instagram(text):
    assert check_prompt(text, "instagram")
    assert check_prompt(text, "social") == []
    assert check_prompt(text, "fanvue") == []


@pytest.mark.parametrize("text", ["looks like Margot Robbie", "celebrity lookalike", "resembling a famous actress"])
def test_real_person_likeness_banned(text):
    assert check_prompt(text, "fanvue")


def test_clean_prompt_passes():
    assert check_prompt("28-year-old woman at her desk, three monitors, morning light, bikini on a boat", "instagram") == []


@pytest.mark.parametrize("text", ["28 year old woman", "29yo", "a 27-year-old engineer", "120 years old statue",
    "28 y.o.", "age 28", "aged 29", "age 200"])
def test_adult_ages_are_not_flagged(text):
    assert check_prompt(text, "instagram") == []


@pytest.mark.parametrize("text", ["20 years old", "9 yo", "13 y o", "1 year old"])
def test_age_regex_boundaries(text):
    assert check_prompt(text, "fanvue")


@pytest.mark.parametrize("text", ["nude_", "NUDE-ish", "Bra!", "teen,", "(TEEN)", "high_school"])
def test_punctuation_and_case_variants(text):
    assert check_prompt(text, "instagram")


def test_violation_names_matched_term():
    out = check_prompt("a School-Girl in lace", "fanvue")
    assert len(out) == 1
    assert "school girl" in out[0]


def test_multiple_violations_listed():
    assert len(check_prompt("teen, topless", "social")) == 2


def test_unknown_tier_raises():
    with pytest.raises(ValueError, match="tier"):
        check_prompt("hello", "onlyfans")  # type: ignore[arg-type]


def test_normalize():
    assert normalize("  School-Girl__OUTFIT \n  x ") == "school girl outfit x"


@pytest.mark.parametrize("text", ["17 y.o.", "15 y.o", "16 yo.", "17yr old", "16 yrs old", "age 16",
    "aged 15", "13 y/o"])
def test_age_spelling_variants_banned_everywhere(text):
    for tier in TIERS:
        assert check_prompt(text, tier)


def test_every_tier_has_rules():
    assert set(get_args(Tier)) == set(TIER_RULES)


@pytest.mark.parametrize("text", [
    "childlike face", "childish pose", "teenaged look", "teeny girl", "lolitas", "loli-style",
    "baby face", "baby-faced", "babyface",
    "17 yrs. old", "16 yrs.old", "age: 16", "aged: 15", "age of 16", "at the age of 17",
    "sixteen year old", "fifteen-year-old",
])
def test_age_stems_and_phrasing_banned_everywhere(text):
    for tier in TIERS:
        assert check_prompt(text, tier), (text, tier)


@pytest.mark.parametrize("text", [
    "nakedness", "Naked", "undressed", "undressing", "UNDRESS", "unclothed",
    "sheer see-through top", "sheer blouse", "see through dress", "see-through", "see_through",
    "transparent shirt",
])
def test_implied_nudity_banned_all_tiers_v1(text):
    for tier in TIERS:
        assert check_prompt(text, tier), (text, tier)


@pytest.mark.parametrize("text", ["28 yrs. old", "age: 28", "age of 29", "at the age of 28", "aged: 27",
    "twenty-eight year old", "a tall glass of water"])
def test_adult_age_phrasing_not_flagged(text):
    assert check_prompt(text, "instagram") == []
