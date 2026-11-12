from __future__ import annotations

import json

from pathlib import Path

import pytest

from comfy_model.scenes import load_scenes
from comfy_model.workflow import PLACEHOLDERS, load_manifest, load_template, model_files, placeholders

QWEN_MANIFEST = Path("pod/qwen_models.yaml")
QWEN_WORKFLOWS = Path("workflows/qwen")
KINDS = ["dataset", "photo"]


def _graph(kind):
    return load_template(kind, QWEN_WORKFLOWS)


def _of(g, cls):
    return [n["inputs"] for n in g.values() if n["class_type"] == cls]


@pytest.mark.parametrize("kind", KINDS)
def test_placeholders_match_batch(kind):
    assert placeholders(_graph(kind)) == PLACEHOLDERS[kind]


@pytest.mark.parametrize("kind", KINDS)
def test_links_valid(kind):
    g = _graph(kind)
    for nid, node in g.items():
        for key, val in node["inputs"].items():
            if isinstance(val, list):
                assert len(val) == 2 and val[0] in g and val[0] != nid, (nid, key)


def test_manifest_covers_exactly_the_graphs():
    extra = [json.loads(Path(f"workflows/qwen/{n}.json").read_text()) for n in ("refine", "seedvr")]
    used = {v.split("/")[-1] for g in [_graph(k) for k in KINDS] + extra for v in model_files(g)}
    assert used == {m.file for m in load_manifest(QWEN_MANIFEST)}


@pytest.mark.parametrize("kind", KINDS)
def test_no_flux_in_qwen_graphs(kind):
    assert not [f for f in model_files(_graph(kind)) if "flux" in f.lower() or "kontext" in f.lower()]


def test_dataset_sampler():
    k = _of(_graph("dataset"), "KSampler")
    assert len(k) == 1
    assert (k[0]["steps"], k[0]["cfg"], k[0]["sampler_name"], k[0]["scheduler"], k[0]["denoise"]) == (
        40, 4, "euler", "simple", 1)
    assert k[0]["seed"] == "{{seed}}"


def test_edit_encoder_has_the_reference():
    g = _graph("dataset")
    scale = next(nid for nid, n in g.items() if n["class_type"] == "FluxKontextImageScale")
    enc = _of(g, "TextEncodeQwenImageEditPlus")
    assert len(enc) == 2 and all(e["image1"] == [scale, 0] for e in enc)
    assert sorted(e["prompt"] for e in enc) == ["", "{{prompt}}"]


def test_photo_has_lora_on_every_sampler():
    g = _graph("photo")
    lora = next(nid for nid, n in g.items() if n["class_type"] == "LoraLoaderModelOnly")
    consumers = _of(g, "KSampler") + _of(g, "FaceDetailer")
    assert len(consumers) == 3 and all(c["model"] == [lora, 0] for c in consumers)


def test_photo_saves_only_the_final_image():
    assert len(_of(_graph("photo"), "SaveImage")) == 1


def test_dataset_scenes():
    s = load_scenes(Path("scenes/dataset_qwen.yaml"), "dataset")
    assert len(s) == 30
    assert all(x.prompt.startswith("Keep the same woman's face and identity,") for x in s)


def test_check_scenes():
    s = load_scenes(Path("scenes/lora_check.yaml"), "photo")
    assert len(s) == 6 and "home-armchair-low-angle" in [x.id for x in s]


def test_extra_face_scenes():
    s = load_scenes(Path("scenes/dataset_qwen_faces.yaml"), "dataset")
    assert len(s) == 12 and len({x.id for x in s}) == 12
    assert all(x.prompt.startswith("Keep the same woman's face and identity,") and "37" in x.prompt for x in s)


def test_round_two_scenes():
    s = load_scenes(Path("scenes/lora_round2.yaml"), "photo")
    ids = {x.id for x in s}
    assert {"armchair-from-floor", "domina-armchair", "home-nightgown-morning"} <= ids
    assert sum(x.count for x in s) == 8


def test_photo_face_pass_works_at_high_resolution():
    d = _of(_graph("photo"), "FaceDetailer")[0]
    assert d["guide_size"] == 1024 and d["max_size"] >= 1536


def test_round_three_scenes():
    s = load_scenes(Path("scenes/lora_round3.yaml"), "photo")
    assert len(s) == 6 and sum(x.count for x in s) == 6
    assert {"selfie-bed-overhead", "gym-mirror-full-body"} <= {x.id for x in s}
