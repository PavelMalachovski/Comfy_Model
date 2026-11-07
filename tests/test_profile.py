import re
from pathlib import Path

import pytest

from comfy_model.profile import Profile, load_profile
from comfy_model.safety import check_prompt


def test_profile_has_adult_anchor():
    p = load_profile()
    assert re.match(r"(3[5-9]|4\d)-year-old woman\b", p.appearance)


def test_profile_text_passes_strictest_tier():
    p = load_profile()
    assert check_prompt(p.appearance + " " + p.style_suffix, "instagram") == []


def test_trigger_only_when_requested():
    p = load_profile()
    assert p.photo_prompt("at desk", use_trigger=True).startswith("ohwxroxana, ")
    assert "ohwxroxana" not in p.photo_prompt("at desk", use_trigger=False)


def test_video_negative_blocks_nudity():
    terms = {t.strip() for t in load_profile().video_negative.split(",")}
    assert {"nude", "naked", "topless", "nipples", "see-through"} <= terms


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
    assert p.name == "Roxana"
    assert p.trigger == "ohwxroxana"


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


BIBLE = Path("character/bible.md")
POST_TIERS = {"Instagram": "instagram", "X": "social", "Reddit": "social", "Telegram": "social"}
MIN_POSTS = {"Instagram": 5, "X": 3, "Reddit": 2, "Telegram": 2}


def _posts_by_platform() -> dict[str, list[str]]:
    """Blockquoted posts under `### <Platform>` headings inside the examples section."""
    text = BIBLE.read_text(encoding="utf-8")
    section = text.split("## Примеры постов", 1)[1].split("\n## ", 1)[0]
    out: dict[str, list[str]] = {}
    for block in re.split(r"^### ", section, flags=re.M)[1:]:
        heading, body = block.split("\n", 1)
        out[heading.strip()] = re.findall(r"^> (.+)$", body, flags=re.M)
    return out


def test_bible_example_posts_pass_their_tier():
    posts = _posts_by_platform()
    for platform, tier in POST_TIERS.items():
        assert len(posts.get(platform, [])) >= MIN_POSTS[platform], platform
        for post in posts[platform]:
            assert check_prompt(post, tier) == [], (platform, post)


def test_bible_has_platform_bios():
    text = BIBLE.read_text(encoding="utf-8")
    section = text.split("## Шаблоны bio", 1)[1].split("\n## ", 1)[0]
    for platform in ("Instagram", "X", "Reddit", "Telegram", "Fanvue"):
        bio = re.search(rf"^### {platform}\n(.+?)(?=^### |\Z)", section, flags=re.M | re.S)
        assert bio and "AI-generated" in bio.group(1), platform
