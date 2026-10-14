"""Scene files: schema and whole-file validation.

A scene file is YAML with an optional top-level ``defaults:`` mapping merged
into every item of ``scenes:``. ``load_scenes`` validates the *entire* file,
collects every problem, and raises a single ``SceneError`` listing them (one per
line, each starting ``scene '<id>': `` or ``file: ``) so nothing is queued from
a half-valid file. The existence of a video scene's ``image`` is *not* checked
here; that happens at run time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

import yaml

from comfy_model.safety import Tier, check_prompt

Kind = Literal["face", "dataset", "photo", "video"]

ASPECTS: dict[str, tuple[int, int]] = {"4:5": (896, 1120), "9:16": (768, 1344), "1:1": (1024, 1024)}
VIDEO_ASPECTS: dict[str, tuple[int, int]] = {"9:16": (704, 1280), "16:9": (1280, 704)}

_SCENE_KEYS = frozenset({"id", "tier", "prompt", "aspect", "count", "seed", "image"})
_DEFAULT_KEYS = _SCENE_KEYS - {"id"}
_TOP_KEYS = frozenset({"defaults", "scenes"})
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TIERS = get_args(Tier)
_KINDS = get_args(Kind)
MAX_COUNT = 16


class SceneError(ValueError):
    """Invalid scene file. Message lists every problem, one per line."""


@dataclass(frozen=True)
class Scene:
    id: str
    tier: Tier
    prompt: str
    aspect: str
    count: int
    seed: int | None
    image: str | None


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _fmt(v: Any) -> str:
    return repr(v)


def _validate_scene(
    raw: Any, index: int, kind: Kind, defaults: dict[str, Any], seen: set[str], errors: list[str]
) -> Scene | None:
    """Validate one scene; append problems to ``errors``. Returns Scene if clean."""
    if not isinstance(raw, dict):
        errors.append(f"scene '#{index}': must be a mapping, got {type(raw).__name__}")
        return None

    sid = raw.get("id")
    usable = isinstance(sid, str) and sid != ""
    label = f"scene '{sid if usable else f'#{index}'}'"
    problems: list[str] = []

    unknown = sorted(str(k) for k in raw if k not in _SCENE_KEYS)
    for k in unknown:
        problems.append(f"unknown key {k!r} (allowed: {', '.join(sorted(_SCENE_KEYS))})")

    if not isinstance(sid, str):
        problems.append("missing or non-string 'id'" if sid is None else f"'id' must be a string, got {_fmt(sid)}")
    elif not _ID_RE.match(sid):
        problems.append(f"'id' {sid!r} must be a slug matching {_ID_RE.pattern} (it becomes a filename)")
    elif sid in seen:
        problems.append(f"duplicate id {sid!r}")
    if usable:
        seen.add(sid)

    merged = {**defaults, **{k: v for k, v in raw.items() if k in _SCENE_KEYS}}
    photo_like = kind != "video"

    tier = merged.get("tier", "instagram")
    tier_ok = tier in _TIERS
    if not tier_ok:
        problems.append(f"unknown tier {_fmt(tier)} (expected one of {', '.join(_TIERS)})")

    prompt = merged.get("prompt")
    prompt_ok = isinstance(prompt, str) and prompt.strip() != ""
    if not prompt_ok:
        problems.append("missing 'prompt' (must be a non-empty string)")

    aspects = ASPECTS if photo_like else VIDEO_ASPECTS
    aspect = merged.get("aspect", "4:5" if photo_like else "9:16")
    if not isinstance(aspect, str) or aspect not in aspects:
        problems.append(f"unknown aspect {_fmt(aspect)} for kind '{kind}' (expected one of {', '.join(aspects)})")

    count = merged.get("count", 4 if photo_like else 1)
    if not _is_int(count) or not 1 <= count <= MAX_COUNT:
        problems.append(f"'count' must be an integer 1-{MAX_COUNT}, got {_fmt(count)}")

    seed = merged.get("seed")
    if seed is not None and (not _is_int(seed) or seed < 0):
        problems.append(f"'seed' must be a non-negative integer, got {_fmt(seed)}")

    image = merged.get("image")
    if kind == "video":
        if not isinstance(image, str) or image.strip() == "":
            problems.append("video scenes require 'image' (path to the source image)")
    elif image is not None:
        problems.append(f"'image' is only allowed for video scenes (kind '{kind}')")

    if tier_ok and prompt_ok:
        problems.extend(check_prompt(prompt, tier))

    errors.extend(f"{label}: {p}" for p in problems)
    if problems:
        return None
    return Scene(id=sid, tier=tier, prompt=prompt, aspect=aspect, count=count, seed=seed, image=image)


def load_scenes(path: Path, kind: Kind) -> list[Scene]:
    """Load and fully validate a scene file; raise one ``SceneError`` for all problems."""
    if kind not in _KINDS:
        raise ValueError(f"unknown kind {kind!r}; expected one of {_KINDS}")
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise SceneError(f"file: cannot read {path}: {e.strerror or e}") from e
    except yaml.YAMLError as e:
        detail = " ".join(str(e).split())
        raise SceneError(f"file: malformed YAML in {path}: {detail}") from e

    if not isinstance(data, dict):
        raise SceneError("file: top level must be a mapping with a 'scenes' list")

    errors: list[str] = []
    for k in sorted(str(k) for k in data if k not in _TOP_KEYS):
        errors.append(f"file: unknown top-level key {k!r} (allowed: defaults, scenes)")

    defaults = data.get("defaults")
    if defaults is None:
        defaults = {}
    elif not isinstance(defaults, dict):
        errors.append(f"file: 'defaults' must be a mapping, got {type(defaults).__name__}")
        defaults = {}
    else:
        for k in sorted(str(k) for k in defaults if k not in _DEFAULT_KEYS):
            errors.append(f"file: unknown key {k!r} in defaults (allowed: {', '.join(sorted(_DEFAULT_KEYS))})")
        defaults = {k: v for k, v in defaults.items() if k in _DEFAULT_KEYS}

    items = data.get("scenes")
    if items is None:
        errors.append("file: missing 'scenes' list")
        items = []
    elif not isinstance(items, list):
        errors.append(f"file: 'scenes' must be a list, got {type(items).__name__}")
        items = []
    elif not items:
        errors.append("file: 'scenes' is empty")

    scenes: list[Scene] = []
    seen: set[str] = set()
    for i, raw in enumerate(items, start=1):
        s = _validate_scene(raw, i, kind, defaults, seen, errors)
        if s is not None:
            scenes.append(s)

    if errors:
        raise SceneError("\n".join(errors))
    return scenes
