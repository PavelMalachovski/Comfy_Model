"""The shipped scene libraries under scenes/ must all validate."""
import re
from pathlib import Path

import pytest

from comfy_model.scenes import load_scenes

SCENES = Path(__file__).resolve().parent.parent / "scenes"

# file name -> (kind, expected tier or None for mixed, minimum scene count)
LIBRARY = {
    "face.yaml": ("face", "instagram", 6),
    "dataset.yaml": ("dataset", "instagram", 40),
    "instagram.yaml": ("photo", "instagram", 30),
    "social.yaml": ("photo", "social", 15),
    "fanvue.yaml": ("photo", "fanvue", 10),
    "video.yaml": ("video", "instagram", 3),
}


@pytest.mark.parametrize("name", LIBRARY)
def test_all_library_files_valid(name):
    kind, tier, minimum = LIBRARY[name]
    scenes = load_scenes(SCENES / name, kind)
    assert len(scenes) >= minimum
    if tier:
        assert {s.tier for s in scenes} == {tier}


def test_face_library_shape():
    scenes = load_scenes(SCENES / "face.yaml", "face")
    assert len(scenes) == 6
    assert {s.count for s in scenes} == {4}


def test_dataset_library_shape():
    scenes = load_scenes(SCENES / "dataset.yaml", "dataset")
    assert len(scenes) == 40
    assert {s.count for s in scenes} == {1}
    assert all(s.prompt.startswith("Keep the same woman's face and identity, ") for s in scenes)


def test_instagram_library_shape():
    scenes = load_scenes(SCENES / "instagram.yaml", "photo")
    assert len(scenes) == 30
    assert {s.count for s in scenes} == {2}


def test_instagram_has_dubai_luxury():
    scenes = load_scenes(SCENES / "instagram.yaml", "photo")
    pat = re.compile(r"dubai|penthouse|yacht|desert|boutique|skyline", re.I)
    assert sum(1 for s in scenes if pat.search(s.prompt)) >= 5


def test_social_library_shape():
    scenes = load_scenes(SCENES / "social.yaml", "photo")
    assert len(scenes) >= 15
    assert sum(1 for s in scenes if "latex" in s.prompt.lower()) >= 5
    assert sum(1 for s in scenes if re.search(r"boots|heels", s.prompt, re.I)) >= 3


@pytest.mark.parametrize("name", ["instagram.yaml", "social.yaml", "fanvue.yaml"])
def test_photo_libraries_mix_aspects(name):
    scenes = load_scenes(SCENES / name, "photo")
    assert {s.aspect for s in scenes} >= {"4:5", "9:16"}


def test_video_library_shape():
    scenes = load_scenes(SCENES / "video.yaml", "video")
    assert 3 <= len(scenes) <= 5
    assert {s.aspect for s in scenes} == {"9:16"}
    assert all(s.image.startswith("../export/") for s in scenes)


@pytest.mark.parametrize("name", LIBRARY)
def test_files_have_header_comment(name):
    text = (SCENES / name).read_text(encoding="utf-8")
    assert text.startswith("#")
    assert "cm " in text.split("\n\n", 1)[0] or "cm " in text[:600]


_RISKY = re.compile(
    r"\b(sheer|see-through|transparent|backlit|silhouette|towel|foam|bubbles|wet|lace|slip)\b", re.I
)


@pytest.mark.parametrize("name", ["instagram.yaml", "social.yaml", "fanvue.yaml"])
def test_no_implied_nudity_cues(name):
    # Cues that tend to render as nudity even though the word filter passes them.
    for s in load_scenes(SCENES / name, "photo"):
        m = _RISKY.search(s.prompt) or _RISKY.search(s.id.replace("-", " "))
        assert m is None, f"{name} scene {s.id!r}: risky cue {m.group(0)!r}"


@pytest.mark.parametrize("name", LIBRARY)
def test_no_hyphen_broken_across_lines(name):
    # A ">-" folded scalar turns "rain-\n dry" into the garbled token "rain- dry".
    kind = LIBRARY[name][0]
    for s in load_scenes(SCENES / name, kind):
        assert not re.search(r"\w- ", s.prompt), f"{name} scene {s.id!r}: {s.prompt!r}"


def test_social_header_mentions_telegram_paid():
    header = (SCENES / "social.yaml").read_text(encoding="utf-8").split("\n\n", 1)[0]
    assert "paid Telegram" in header and "X" in header and "Reddit" in header


def test_headers_use_roxana_lora():
    for name in ("instagram.yaml", "social.yaml", "fanvue.yaml"):
        assert "--lora ohwxroxana_v1.safetensors" in (SCENES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["instagram.yaml", "social.yaml", "fanvue.yaml"])
def test_robes_have_stated_underlayer(name):
    # A robe with nothing stated under it tends to render open over bare skin.
    for s in load_scenes(SCENES / name, "photo"):
        if re.search(r"\brobes?\b", s.prompt, re.I):
            assert re.search(r"\brobe\b[^.]*\bover\b", s.prompt, re.I), f"{name} scene {s.id!r}"
