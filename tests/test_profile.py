import re
from pathlib import Path

import pytest

from comfy_model.profile import Profile, load_profile
from comfy_model.safety import check_prompt


def test_profile_has_adult_anchor():
    p = load_profile()
    assert re.search(r"\b(2[5-9]|[3-9]\d)-year-old (?:\w+ )?woman\b", p.appearance)
    assert p.appearance.startswith("28-year-old Lithuanian woman")


def test_profile_text_passes_strictest_tier():
    p = load_profile()
    assert check_prompt(p.appearance + " " + p.style_suffix, "instagram") == []


def test_trigger_only_when_requested():
    p = load_profile()
    assert p.photo_prompt("at desk", use_trigger=True).startswith("ohwxgreta, ")
    assert "ohwxgreta" not in p.photo_prompt("at desk", use_trigger=False)


def test_video_negative_blocks_minors():
    neg = load_profile().video_negative
    for term in ("child", "teen", "underage", "deformed", "extra limbs", "blurry"):
        assert term in neg


def test_photo_prompt_layout():
    p = Profile(name="N", trigger="trg", appearance="A", style_suffix="S", video_negative="V")
    assert p.photo_prompt("scene", use_trigger=True) == "trg, A, scene, S"
    assert p.photo_prompt("scene", use_trigger=False) == "A, scene, S"


def test_name_and_trigger():
    p = load_profile()
    assert p.name == "Greta Vaitkutė"
    assert p.trigger == "ohwxgreta"


def _write(tmp_path: Path, **overrides) -> Path:
    data = {
        "name": "N", "trigger": "t", "appearance": "A", "style_suffix": "S", "video_negative": "V",
    }
    data.update(overrides)
    lines = [f"{k}: {v!r}" for k, v in data.items() if v is not None]
    p = tmp_path / "profile.yaml"
    p.write_text("\n".join(lines) + "\n")
    return p


def test_missing_key_names_it(tmp_path: Path):
    p = _write(tmp_path, style_suffix=None)
    with pytest.raises(ValueError, match="style_suffix"):
        load_profile(p)


def test_unknown_key_rejected(tmp_path: Path):
    p = _write(tmp_path, extra="x")
    with pytest.raises(ValueError, match="extra"):
        load_profile(p)


def test_missing_file_is_clear(tmp_path: Path):
    with pytest.raises(ValueError, match="not found"):
        load_profile(tmp_path / "nope.yaml")


def test_non_string_value_rejected(tmp_path: Path):
    p = tmp_path / "p.yaml"
    p.write_text("name: N\ntrigger: t\nappearance: 5\nstyle_suffix: S\nvideo_negative: V\n")
    with pytest.raises(ValueError, match="appearance"):
        load_profile(p)


def test_bible_example_posts_pass_instagram_rules():
    text = Path("character/bible.md").read_text(encoding="utf-8")
    posts = re.findall(r"^> (.+)$", text, flags=re.M)
    assert len(posts) == 10
    for post in posts:
        assert check_prompt(post, "instagram") == [], post
