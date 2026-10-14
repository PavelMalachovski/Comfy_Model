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
    "instagram.yaml": ("photo", "instagram", 20),
    "social.yaml": ("photo", "social", 15),
    "fanvue.yaml": ("photo", "fanvue", 15),
    "video.yaml": ("video", None, 6),
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


def test_instagram_has_it_content():
    scenes = load_scenes(SCENES / "instagram.yaml", "photo")
    pat = re.compile(r"monitor|laptop|terminal|server|keyboard|on-call", re.I)
    assert sum(1 for s in scenes if pat.search(s.prompt)) >= 5


@pytest.mark.parametrize("name", ["instagram.yaml", "social.yaml", "fanvue.yaml"])
def test_photo_libraries_mix_aspects(name):
    scenes = load_scenes(SCENES / name, "photo")
    assert {s.aspect for s in scenes} >= {"4:5", "9:16"}


def test_video_library_shape():
    scenes = load_scenes(SCENES / "video.yaml", "video")
    assert {s.aspect for s in scenes} == {"9:16"}
    assert all(s.image.startswith("../export/") for s in scenes)


@pytest.mark.parametrize("name", LIBRARY)
def test_files_have_header_comment(name):
    text = (SCENES / name).read_text(encoding="utf-8")
    assert text.startswith("#")
    assert "cm " in text.split("\n\n", 1)[0] or "cm " in text[:600]
