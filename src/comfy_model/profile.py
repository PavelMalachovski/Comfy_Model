"""Persona prompt profile (character/profile.yaml)."""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Profile:
    name: str
    trigger: str
    appearance: str
    style_suffix: str
    video_negative: str

    def photo_prompt(self, scene_prompt: str, use_trigger: bool) -> str:
        """``[trigger, ]appearance, scene, style_suffix``; trigger only when the LoRA is loaded."""
        prefix = f"{self.trigger}, " if use_trigger else ""
        return f"{prefix}{self.appearance}, {scene_prompt}, {self.style_suffix}"


def load_profile(path: Path = Path("character/profile.yaml")) -> Profile:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise ValueError(f"profile file not found: {path}") from None
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping at top level")
    names = [f.name for f in fields(Profile)]
    missing = [n for n in names if n not in raw]
    if missing:
        raise ValueError(f"{path}: missing key(s): {', '.join(missing)}")
    unknown = sorted(set(raw) - set(names))
    if unknown:
        raise ValueError(f"{path}: unknown key(s): {', '.join(map(str, unknown))}")
    for n in names:
        if not isinstance(raw[n], str) or not raw[n].strip():
            raise ValueError(f"{path}: key {n!r} must be a non-empty string")
    # Folded YAML scalars may carry newlines; collapse to single-line prompt text.
    return Profile(**{n: " ".join(raw[n].split()) for n in names})
