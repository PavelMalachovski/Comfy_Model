import pytest

from comfy_model.safety import check_prompt, normalize

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


@pytest.mark.parametrize("text", ["28 year old woman", "29yo", "a 27-year-old engineer", "120 years old statue"])
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
