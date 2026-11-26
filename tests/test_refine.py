from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

from comfy_model.batch import BatchReport
from comfy_model.cli import app
from comfy_model.comfy_client import ComfyError, OutputFile
from comfy_model.lora import _manifest_prompts
from comfy_model.refine import MAX_CONSECUTIVE_FAILURES, TEXTURE_PROMPT, refine_dataset
from comfy_model.workflow import load_manifest, model_files, placeholders, render

GRAPH_DIR = Path("workflows/qwen")


class FakeClient:
    def __init__(self, fail=None):
        self.queued, self.uploads, self._fail = [], [], fail

    def upload_image(self, path, name=None):
        self.uploads.append(Path(path))
        return name or Path(path).name

    def queue(self, wf):
        self.queued.append(wf)
        if isinstance(self._fail, ComfyError):
            raise self._fail
        return f"p{len(self.queued)}"

    def wait(self, prompt_id, timeout_s=900):
        if isinstance(self._fail, TimeoutError):
            raise self._fail
        return {"id": prompt_id}

    def outputs(self, entry):
        return [OutputFile("x_00001_.png", "", "output")]

    def download(self, f, dest):
        Image.new("RGB", (64, 64), "white").save(dest)
        return dest


def _src(tmp_path, names=("a_01.png", "b_01.png", "c_01.png")):
    src = tmp_path / "src"
    src.mkdir()
    with (src / "manifest.jsonl").open("w") as m:
        for n in names:
            Image.new("RGB", (64, 64), "red").save(src / n)
            m.write(json.dumps({"file": n, "prompt": f"Keep the same woman's face and identity, scene {n}"}) + "\n")
    return src


def _prompts(wf):
    return [n["inputs"]["text"] for n in wf.values() if n["class_type"] == "CLIPTextEncode"]


def test_refine_graph_contract():
    g = json.loads((GRAPH_DIR / "refine.json").read_text())
    assert placeholders(g) == {"prompt", "seed", "image", "filename_prefix"}
    ks = [n["inputs"] for n in g.values() if n["class_type"] == "KSampler"]
    assert len(ks) == 1 and ks[0]["denoise"] == 0.25
    assert "FaceDetailer" in {n["class_type"] for n in g.values()}
    assert {v.split("/")[-1] for v in model_files(g)} <= {m.file for m in load_manifest(Path("pod/qwen_models.yaml"))}
    assert render(g, {"prompt": "p", "seed": 1, "image": "i.png", "filename_prefix": "f"})


def test_refines_every_image_with_caption_and_texture(tmp_path):
    c = FakeClient()
    report = refine_dataset(_src(tmp_path), tmp_path / "dst", c)
    assert isinstance(report, BatchReport) and len(report.done) == 3
    assert (tmp_path / "dst" / "a_01.png").is_file()
    assert any("scene a_01.png" in p and TEXTURE_PROMPT in p for p in _prompts(c.queued[0]))
    assert not any("Keep the same woman" in p for p in _prompts(c.queued[0]))


def test_output_manifest_gives_prepare_the_original_captions(tmp_path):
    refine_dataset(_src(tmp_path), tmp_path / "dst", FakeClient())
    assert _manifest_prompts(tmp_path / "dst")["a_01.png"] == "scene a_01.png"


def test_rerun_skips_finished_images(tmp_path):
    src = _src(tmp_path)
    refine_dataset(src, tmp_path / "dst", FakeClient())
    again = FakeClient()
    report = refine_dataset(src, tmp_path / "dst", again)
    assert again.queued == [] and len(report.skipped) == 3


def test_only_culled_survivors_are_refined(tmp_path):
    src = _src(tmp_path)
    (src / "b_01.png").unlink()
    c = FakeClient()
    assert len(refine_dataset(src, tmp_path / "dst", c).done) == 2


def test_validation_error_stops(tmp_path):
    c = FakeClient(fail=ComfyError("missing", is_validation=True))
    with pytest.raises(ComfyError):
        refine_dataset(_src(tmp_path), tmp_path / "dst", c)
    assert len(c.queued) == 1


def test_repeated_errors_stop(tmp_path):
    names = tuple(f"n{i}_01.png" for i in range(6))
    c = FakeClient(fail=ComfyError("oom"))
    report = refine_dataset(_src(tmp_path, names), tmp_path / "dst", c)
    assert len(c.queued) == MAX_CONSECUTIVE_FAILURES and report.aborted


def test_timeout_stops(tmp_path):
    c = FakeClient(fail=TimeoutError("slow"))
    report = refine_dataset(_src(tmp_path), tmp_path / "dst", c)
    assert report.aborted and len(c.queued) == 1


def test_empty_source_is_refused(tmp_path):
    (tmp_path / "e").mkdir()
    with pytest.raises(ValueError, match="no images"):
        refine_dataset(tmp_path / "e", tmp_path / "dst", FakeClient())


def test_cli_registered():
    assert CliRunner().invoke(app, ["lora", "refine", "--help"]).exit_code == 0


def test_texture_prompt_keeps_the_makeup():
    assert "lipstick" in TEXTURE_PROMPT and "makeup" in TEXTURE_PROMPT
    assert "no retouching" not in TEXTURE_PROMPT




def test_texture_prompt_pins_age_and_face():
    for word in ("37-year-old", "dark brown eyes", "defined cheekbones", "pores", "naturally plump full lips"):
        assert word in TEXTURE_PROMPT
    for ageing in ("fine lines", "freckles", "unevenness"):
        assert ageing not in TEXTURE_PROMPT


def test_face_pass_strength_balances_skin_and_identity():
    g = json.loads((GRAPH_DIR / "refine.json").read_text())
    assert next(n["inputs"] for n in g.values() if n["class_type"] == "FaceDetailer")["denoise"] == 0.27


def test_seedvr_graph_contract():
    g = json.loads((GRAPH_DIR / "seedvr.json").read_text())
    assert placeholders(g) == {"seed", "image", "filename_prefix"}
    classes = {n["class_type"] for n in g.values()}
    assert {"SeedVR2LoadDiTModel", "SeedVR2LoadVAEModel", "SeedVR2VideoUpscaler", "SaveImage"} <= classes
    manifest = {m.file: m for m in load_manifest(Path("pod/qwen_models.yaml"))}
    for n in g.values():
        if n["class_type"].startswith("SeedVR2Load"):
            assert manifest[n["inputs"]["model"]].dest == "SEEDVR2"


def test_refine_with_seedvr_graph_drops_the_prompt(tmp_path):
    c = FakeClient()
    report = refine_dataset(_src(tmp_path), tmp_path / "dst", c, graph_path=GRAPH_DIR / "seedvr.json")
    assert len(report.done) == 3
    up = next(n for n in c.queued[0].values() if n["class_type"] == "SeedVR2VideoUpscaler")
    assert isinstance(up["inputs"]["seed"], int)


def test_room_graph_contract():
    g = json.loads((GRAPH_DIR / "room.json").read_text())
    assert all(isinstance(n, dict) for n in g.values()), "ComfyUI rejects non-node keys (e.g. _comment)"
    assert placeholders(g) == {"image", "room_image", "seed", "filename_prefix"}
    enc = next(n for n in g.values() if isinstance(n, dict) and n.get("class_type") == "TextEncodeQwenImageEditPlus"
               and n["inputs"]["prompt"])
    assert "image1" in enc["inputs"] and "image2" in enc["inputs"]


def test_refine_with_room_uploads_the_plate_once(tmp_path):
    plate = tmp_path / "plate.png"
    Image.new("RGB", (64, 96)).save(plate)
    c = FakeClient()
    report = refine_dataset(_src(tmp_path), tmp_path / "dst", c, graph_path=GRAPH_DIR / "room.json", room=plate)
    assert len(report.done) == 3
    assert c.uploads.count(plate) == 1
    loads = [n["inputs"]["image"] for n in c.queued[0].values() if isinstance(n, dict) and n.get("class_type") == "LoadImage"]
    assert len(loads) == 2 and any("plate.png" in x for x in loads)


def test_room_graph_needs_a_plate_and_others_refuse_one(tmp_path):
    src = _src(tmp_path)
    with pytest.raises(ValueError, match="--room"):
        refine_dataset(src, tmp_path / "dst", FakeClient(), graph_path=GRAPH_DIR / "room.json")
    plate = tmp_path / "plate.png"
    Image.new("RGB", (8, 8)).save(plate)
    with pytest.raises(ValueError, match="room_image"):
        refine_dataset(src, tmp_path / "dst2", FakeClient(), graph_path=GRAPH_DIR / "seedvr.json", room=plate)
