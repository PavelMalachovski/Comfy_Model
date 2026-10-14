"""Prompt safety rules. Pure functions, no I/O.

Rules are word-boundary regexes over *normalized* text (lowercase, ``-``/``_``
turned into spaces, whitespace collapsed), so "School-Girl", "SCHOOL_GIRL" and
"school  girl" are all the same term. Rules are keyed by tier; to relax a tier
later (e.g. explicit Fanvue) edit its entry in ``TIER_RULES``.
"""
from __future__ import annotations

import re
from typing import Literal, get_args

Tier = Literal["instagram", "social", "fanvue"]

Rule = tuple[str, "re.Pattern[str]"]  # (category, pattern)


def normalize(text: str) -> str:
    """Lowercase, replace ``-`` and ``_`` with a space, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", text.lower())).strip()


def _words(*terms: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(terms) + r")\b")


# Persona is clearly adult. Anything suggesting minors is banned on every tier.
# Stems (``child\w*``, ``teen\w*``, ``loli\w*``) also catch "childlike", "teenaged",
# "lolitas"; a stem may over-match a harmless word, which is the safe direction.
_AGE_NUM = r"(?:[1-9]|1\d|20)"
_AGE_WORD = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)"
_AGE = (
    "age",
    _words(
        r"teen\w*", r"school\s?(?:girls?|boys?|kids?|uniforms?)",
        r"high\s?school(?:er)?", r"middle\s?school", r"junior\s?high", r"pre\s?teen\w*",
        r"loli\w*", r"shota", r"jail\s?bait", r"under\s?age(?:d)?",
        r"young\s(?:girls?|boys?|looking)", r"little\s(?:girls?|boys?)", r"child\w*",
        r"kids?", r"barely\slegal", r"baby\s?faced?",
        # stated age 1-20 ("18yo", "17 y.o.", "16 yrs old", "17 yrs. old", "13 y/o", "17 year old")
        _AGE_NUM + r"\s?(?:y[./\s]{0,2}o|y(?:ea)?rs?\.?\s?old)",
        # "sixteen year old"; not the units of "twenty eight" (tens words end in "ty")
        r"(?<!ty\s)" + _AGE_WORD + r"\s(?:y(?:ea)?rs?\.?\s?old|y[./\s]{0,2}o)",
        # "age 16", "aged 15", "age: 16", "age of 16"
        r"ages?d?:?\s?(?:of\s)?" + _AGE_NUM,
    ),
)

# v1: no nudity on any tier, including cues that render as nudity (sheer, see-through).
_NUDITY = (
    "nudity",
    _words(
        r"nude", r"nudes", r"nudity", r"nake\w*", r"topless", r"bottomless",
        r"nipples?", r"areolas?", r"explicit", r"nsfw", r"porn(?:ographic)?",
        r"genitals?", r"pussy", r"bare\sbreasts?", r"undress\w*", r"unclothed",
        r"see\s?through", r"transparent", r"sheer",
    ),
)

# Instagram tier additionally bans lingerie / underwear.
_LINGERIE = (
    "lingerie",
    _words(
        r"lingerie", r"bras?", r"brassieres?", r"panties", r"panty", r"underwear",
        r"thongs?", r"g\sstrings?", r"negligee", r"corsets?", r"garters?",
    ),
)

# No real-person likeness, on any tier.
_LIKENESS = (
    "real-person likeness",
    _words(
        r"looks?\slike", r"look\s?alikes?", r"resembl(?:e|es|ing)", r"celebrit(?:y|ies)",
        r"famous\s(?:actress|actor|singer|model|person|celebrity)",
    ),
)

_BASE: list[Rule] = [_AGE, _NUDITY, _LIKENESS]

TIER_RULES: dict[str, list[Rule]] = {
    "instagram": [*_BASE, _LINGERIE],
    "social": list(_BASE),
    "fanvue": list(_BASE),
}


def check_prompt(text: str, tier: Tier) -> list[str]:
    """Return human-readable violations for ``text`` on ``tier``; empty list = OK."""
    if tier not in TIER_RULES:
        raise ValueError(f"unknown tier {tier!r}; expected one of {get_args(Tier)}")
    norm = normalize(text)
    violations: list[str] = []
    for category, pattern in TIER_RULES[tier]:
        for m in pattern.finditer(norm):
            violations.append(f"banned {category} term {m.group(0)!r} (tier {tier})")
    return violations
