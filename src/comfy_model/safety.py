"""Prompt safety rules. Pure functions, no I/O.

Rules are word-boundary regexes over *normalized* text (lowercase, ``-``/``_``
turned into spaces, whitespace collapsed), so "School-Girl", "SCHOOL_GIRL" and
"school  girl" are all the same term. Tiers: ``instagram`` (SFW showcase: no
lingerie, no fetish cues), ``social`` (X, Reddit, paid Telegram) and ``fanvue``
(full nudity allowed: breasts, buttocks, genitals; sexual acts still banned).
Minors and real-person likeness are banned on every tier. Rules are keyed by
tier; edit ``TIER_RULES`` to change a tier.
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

# Visible nudity, including genitals and cues that render as nudity (sheer, see-through).
# Banned on instagram and social; allowed on fanvue (owner decision, 16 Nov 2026).
# Render on the Mac only (RunPod ToS).
_NUDITY = (
    "nudity",
    _words(
        r"nude", r"nudes", r"nudity", r"nake\w*",
        r"nipples?", r"areolas?", r"explicit", r"nsfw",
        r"genitals?", r"genitalia", r"vulva", r"labia", r"pussy",
        r"undress\w*", r"unclothed",
        r"see\s?through", r"transparent", r"sheer",
    ),
)

# Sexual acts and porn: banned on every tier, fanvue included.
_SEX = (
    "sexual act",
    _words(
        r"porn\w*", r"sex", r"sexual\s(?:act|intercourse|activity)", r"intercourse",
        r"masturbat\w*", r"penetrat\w*", r"orgasm\w*", r"cum(?:shots?|ming)?", r"blow\s?jobs?",
        r"oral\ssex", r"fingering", r"dildos?", r"vibrators?", r"sex\stoys?",
    ),
)

# Implied topless: no top, breasts covered by her hands or arms, nothing visible.
# Banned on instagram and social; allowed on fanvue only (owner decision, 14 Nov 2026).
# Render these on the Mac only (RunPod ToS) and cull any frame where anything shows.
_TOPLESS = (
    "topless",
    _words(r"topless", r"bare\sbreasts?", r"bare\schest(?:ed)?", r"hand\s?bra"),
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

# Instagram is the SFW showcase: no fetish cues (latex, feet, slave/mistress roleplay,
# hosiery). X, Reddit, Telegram and Fanvue allow them.
_FETISH = (
    "fetish",
    _words(
        r"latex", r"pvc", r"vinyl(?!\srecords?)", r"rubber(?!\splants?)",
        r"foot\s?worship", r"feet", r"foot(?!\s(?:of|tall|long))", r"footstool",
        r"barefoot", r"pedicure\w*", r"(?<!red\s)soles?", r"(?<!pointed\s)(?<!square\s)(?<!almond\s)(?<!head\sto\s)toes?",
        r"slaves?", r"mistress\w*", r"dominatrix", r"femdom", r"dommes?", r"submissive\w*",
        r"fetish\w*", r"bdsm", r"bondage", r"riding\s?crop", r"whips?",
        r"(?:leather|dog|spiked|slave|o\s?ring|pet)\s?collars?", r"collars?\s(?:and|&)\s(?:a\s)?leash", r"leash\w*",
        r"handcuff\w*", r"harness\w*", r"(?:ball\s)?gags?", r"(?<!gold\s)(?<!silver\s)chain(?:s|ed)?(?!\s(?:necklace|bracelet))", r"spank\w*", r"paddles?",
        r"worship\w*", r"humiliat\w*", r"trampl\w*", r"chastity", r"findom", r"pay\s?pigs?",
        r"catsuits?", r"stockings?", r"fishnets?", r"pantyhose", r"nylons", r"hosiery",
        r"kneel\w*", r"on\s(?:his|their|your|my)\sknees",
    ),
)

_BASE: list[Rule] = [_AGE, _SEX, _LIKENESS]

# Rear nudity: no bottom, buttocks bare, seen from behind, genitals never visible.
# Banned on instagram and social; allowed on fanvue only (owner decision, 14 Nov 2026).
# Same handling as _TOPLESS: Mac only, cull any frame where anything else shows.
_REAR = (
    "rear nudity",
    _words(r"bottomless", r"bare\s(?:buttocks|bottom|butt)", r"no\s(?:panties|underwear|bikini\sbottom)"),
)

TIER_RULES: dict[str, list[Rule]] = {
    "instagram": [*_BASE, _NUDITY, _TOPLESS, _REAR, _LINGERIE, _FETISH],
    "social": [*_BASE, _NUDITY, _TOPLESS, _REAR],
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
