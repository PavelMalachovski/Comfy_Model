from __future__ import annotations

from comfy_model.bakeoff import BAKEOFF_PROFILE, BAKEOFF_SCENES
from pathlib import Path

from comfy_model.profile import load_profile
from comfy_model.safety import check_prompt
from comfy_model.scenes import load_scenes


def _scenes():
    return load_scenes(BAKEOFF_SCENES, "face")


def test_six_scenes_right_tiers():
    tiers = [s.tier for s in _scenes()]
    assert tiers.count("instagram") == 4 and tiers.count("social") == 2
    assert all(s.aspect == "4:5" and s.count == 1 and s.seed is not None for s in _scenes())


def test_every_scene_has_its_own_seed():
    seeds = [s.seed for s in _scenes()]
    assert len(set(seeds)) == 6


def test_social_prompts_verbatim():
    social = {s.id: s.prompt for s in load_scenes(Path("scenes/social.yaml"), "photo")}
    mine = {s.id: s.prompt for s in _scenes() if s.tier == "social"}
    assert set(mine) == {"latex-dress-penthouse", "pov-from-floor"}
    assert all(mine[k] == social[k] for k in mine)


def test_full_prompts_pass_their_tier():
    profile = load_profile(BAKEOFF_PROFILE)
    for s in _scenes():
        assert check_prompt(profile.photo_prompt(s.prompt, False), s.tier) == [], s.id


def test_profile_states_adult_age():
    assert load_profile(BAKEOFF_PROFILE).appearance.startswith("42-year-old woman")


# -- graphs ---------------------------------------------------------------------
import pytest  # noqa: E402

from comfy_model.bakeoff import (  # noqa: E402
    BAKEOFF_MANIFEST,
    CANDIDATES,
    GRAPH_PLACEHOLDERS,
    load_graph,
)
from comfy_model.workflow import TemplateError, load_manifest, model_files, placeholders  # noqa: E402

NAMES = [c.name for c in CANDIDATES]
LATENT = ["qwen_2512", "z_image", "z_image_turbo"]


def _of(g, cls):
    return {nid: n for nid, n in g.items() if n["class_type"] == cls}


def _detailer_id(g):
    ids = list(_of(g, "FaceDetailer"))
    assert len(ids) == 1
    return ids[0]


@pytest.mark.parametrize("name", NAMES)
def test_graph_placeholders(name):
    assert placeholders(load_graph(name)) == GRAPH_PLACEHOLDERS


@pytest.mark.parametrize("name", NAMES)
def test_graph_links_valid(name):
    g = load_graph(name)
    for nid, node in g.items():
        for key, val in node["inputs"].items():
            if isinstance(val, list):
                assert len(val) == 2 and val[0] in g and val[0] != nid, (nid, key)


@pytest.mark.parametrize("name", NAMES)
def test_graph_models_are_in_bakeoff_manifest(name):
    used = {f.split("/")[-1] for f in model_files(load_graph(name))}
    assert used and used <= {m.file for m in load_manifest(BAKEOFF_MANIFEST)}


def test_manifest_has_no_unused_models():
    used = {f.split("/")[-1] for c in CANDIDATES for f in model_files(load_graph(c.name))}
    assert used == {m.file for m in load_manifest(BAKEOFF_MANIFEST)}


@pytest.mark.parametrize("name", NAMES)
def test_face_crop_save_uses_cropped_refined(name):
    g = load_graph(name)
    saves = {n["inputs"]["filename_prefix"]: n["inputs"]["images"] for n in _of(g, "SaveImage").values()}
    d = _detailer_id(g)
    assert saves == {"{{filename_prefix}}": [d, 0], "{{filename_prefix_face}}": [d, 1]}


def test_base_sizes():
    assert {(c.name, c.width, c.height) for c in CANDIDATES} == {
        ("qwen_2512", 1024, 1280), ("z_image", 1024, 1280),
        ("z_image_turbo", 1024, 1280), ("hidream_o1", 1792, 2304),
    }


@pytest.mark.parametrize("name,steps,cfg,sampler,sched,shift", [
    ("qwen_2512", 50, 4, "euler", "simple", 3.1),
    ("z_image", 25, 4, "res_multistep", "simple", 3),
    ("z_image_turbo", 8, 1, "res_multistep", "simple", 3),
])
def test_base_sampler_settings(name, steps, cfg, sampler, sched, shift):
    g = load_graph(name)
    base = [n["inputs"] for n in _of(g, "KSampler").values() if n["inputs"]["denoise"] == 1.0]
    assert len(base) == 1
    b = base[0]
    assert (b["steps"], b["cfg"], b["sampler_name"], b["scheduler"]) == (steps, cfg, sampler, sched)
    assert b["seed"] == "{{seed}}"
    assert list(_of(g, "ModelSamplingAuraFlow").values())[0]["inputs"]["shift"] == shift


@pytest.mark.parametrize("name", LATENT)
def test_refine_pass(name):
    g = load_graph(name)
    scale = list(_of(g, "ImageScaleBy").values())[0]["inputs"]
    assert (scale["upscale_method"], scale["scale_by"]) == ("lanczos", 1.5)
    assert [n["inputs"]["denoise"] for n in _of(g, "KSampler").values()].count(0.25) == 1


@pytest.mark.parametrize("name,steps", [("qwen_2512", 25), ("z_image", 20), ("z_image_turbo", 8), ("hidream_o1", 20)])
def test_face_detailer_settings(name, steps):
    g = load_graph(name)
    d = g[_detailer_id(g)]["inputs"]
    assert (d["steps"], d["guide_size"], d["denoise"]) == (steps, 768, 0.35)
    assert d["seed"] == "{{seed}}"


def test_hidream_generates_at_full_size_without_refine():
    g = load_graph("hidream_o1")
    assert not _of(g, "ImageScaleBy") and not _of(g, "KSampler")
    assert list(_of(g, "BasicScheduler").values())[0]["inputs"]["steps"] == 40
    latent = list(_of(g, "EmptyHiDreamO1LatentImage").values())[0]["inputs"]
    assert (latent["width"], latent["height"]) == ("{{width}}", "{{height}}")


def test_unknown_candidate_rejected():
    with pytest.raises(TemplateError):
        load_graph("flux")


# -- runner ---------------------------------------------------------------------
import json  # noqa: E402

from PIL import Image  # noqa: E402

import comfy_model.bakeoff as bk  # noqa: E402
from comfy_model.comfy_client import ComfyError, OutputFile  # noqa: E402

FULL = OutputFile("x_00001_.png", "", "output")
CROP = OutputFile("x_face_00001_.png", "", "output")
FRAMES = 6


class FakeClient:
    """Records queued graphs; saves real images so sheets can open them."""

    def __init__(self, outputs=(FULL, CROP), fail=None, crop_size=256):
        self.queued, self._outputs, self._fail, self._crop = [], list(outputs), fail, crop_size

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
        return self._outputs

    def download(self, f, dest):
        size = self._crop if "_face_" in f.filename else 64
        Image.new("RGB", (size, size), "white").save(dest)
        return dest


def _seeds(wfs):
    return [next(n["inputs"]["seed"] for n in wf.values() if "seed" in n["inputs"]) for wf in wfs]


def test_same_seeds_across_candidates(tmp_path):
    a, b = FakeClient(), FakeClient()
    bk.run_bakeoff(["z_image"], a, tmp_path / "1")
    bk.run_bakeoff(["z_image_turbo"], b, tmp_path / "2")
    assert len(a.queued) == FRAMES and _seeds(a.queued) == _seeds(b.queued)
    assert _seeds(a.queued)[:5] == [1001, 2001, 3001, 4001, 5001]


def test_files_land_per_candidate(tmp_path):
    bk.run_bakeoff(["z_image"], FakeClient(), tmp_path, limit=1)
    assert (tmp_path / "z_image" / "mirror-selfie-home_01.png").is_file()
    assert (tmp_path / "z_image" / "mirror-selfie-home_01_face.png").is_file()


def test_candidate_size_reaches_the_graph(tmp_path):
    c = FakeClient()
    bk.run_bakeoff(["hidream_o1"], c, tmp_path, limit=1)
    latent = next(n for n in c.queued[0].values() if n["class_type"] == "EmptyHiDreamO1LatentImage")
    assert (latent["inputs"]["width"], latent["inputs"]["height"]) == (1792, 2304)


def test_rerun_skips_finished_frames(tmp_path):
    bk.run_bakeoff(["z_image"], FakeClient(), tmp_path)
    again = FakeClient()
    report = bk.run_bakeoff(["z_image"], again, tmp_path)
    assert again.queued == [] and len(report.skipped) == FRAMES


def test_limit_is_per_candidate_and_counts_only_new_frames(tmp_path):
    c = FakeClient()
    bk.run_bakeoff(["z_image", "z_image_turbo"], c, tmp_path, limit=1)
    assert len(c.queued) == 2
    bk.run_bakeoff(["z_image"], c, tmp_path, limit=1)
    assert len(list((tmp_path / "z_image").glob("*_0?.png"))) == 2


def _rows(d):
    return [json.loads(x) for x in (d / "manifest.jsonl").read_text().splitlines()]


def test_absent_face_output_keeps_frame(tmp_path):
    report = bk.run_bakeoff(["z_image"], FakeClient(outputs=[FULL]), tmp_path, limit=2)
    assert len(report.done) == 2 and report.failed == []
    assert _rows(tmp_path / "z_image")[0]["no_face"] is True


def test_detailer_placeholder_crop_counts_as_no_face(tmp_path):
    # FaceDetailer returns a 64x64 black image when it detects nothing.
    bk.run_bakeoff(["z_image"], FakeClient(crop_size=64), tmp_path, limit=1)
    assert _rows(tmp_path / "z_image")[0]["no_face"] is True
    assert not (tmp_path / "z_image" / "mirror-selfie-home_01_face.png").exists()


def test_validation_error_stops_run(tmp_path):
    c = FakeClient(fail=ComfyError("model missing", is_validation=True))
    with pytest.raises(ComfyError, match="model missing"):
        bk.run_bakeoff(["z_image"], c, tmp_path)
    assert len(c.queued) == 1


def test_other_comfy_error_is_recorded_and_run_continues(tmp_path):
    c = FakeClient(fail=ComfyError("oom"))
    report = bk.run_bakeoff(["z_image"], c, tmp_path, limit=3)
    assert len(report.failed) == 3


def test_timeout_stops_run(tmp_path):
    c = FakeClient(fail=TimeoutError("slow"))
    report = bk.run_bakeoff(["z_image", "z_image_turbo"], c, tmp_path)
    assert report.aborted and len(c.queued) == 1


def test_prompt_violation_queues_nothing(tmp_path, monkeypatch):
    bad = tmp_path / "p.yaml"
    text = BAKEOFF_PROFILE.read_text().replace("42-year-old woman,", "42-year-old woman, nude,", 1)
    bad.write_text(text)
    monkeypatch.setattr(bk, "BAKEOFF_PROFILE", bad)
    c = FakeClient()
    with pytest.raises(ValueError, match="nude"):
        bk.run_bakeoff(["z_image"], c, tmp_path / "o")
    assert c.queued == []


def test_unknown_candidate_queues_nothing(tmp_path):
    c = FakeClient()
    with pytest.raises(ValueError, match="flux"):
        bk.run_bakeoff(["flux"], c, tmp_path)
    assert c.queued == []


# -- sheets ---------------------------------------------------------------------
def _run_all(out):
    bk.run_bakeoff([c.name for c in CANDIDATES], FakeClient(), out, limit=4)


def test_sheets_are_blind(tmp_path):
    _run_all(tmp_path)
    sheets = bk.make_sheets(tmp_path)
    names = {p.name for p in sheets.iterdir()}
    assert "mirror-selfie-home.jpg" in names and "mirror-selfie-home_faces.jpg" in names
    assert not any(c.name in n for c in CANDIDATES for n in names)
    key = json.loads((tmp_path / "key.json").read_text())
    assert sorted(key) == ["A", "B", "C", "D"] and set(key.values()) == set(NAMES)
    assert (tmp_path / "key.json").parent != sheets


def test_sheet_letters_stable(tmp_path):
    _run_all(tmp_path)
    bk.make_sheets(tmp_path)
    first = (tmp_path / "key.json").read_text()
    bk.make_sheets(tmp_path)
    assert (tmp_path / "key.json").read_text() == first


def test_sheet_missing_frames_do_not_raise(tmp_path):
    bk.run_bakeoff(["z_image"], FakeClient(outputs=[FULL]), tmp_path, limit=1)
    sheet = bk.make_sheets(tmp_path) / "car-back-seat.jpg"
    assert sheet.is_file()


def test_sheets_without_any_frames_fail_clearly(tmp_path):
    with pytest.raises(ValueError, match="no frames"):
        bk.make_sheets(tmp_path)


# -- CLI ------------------------------------------------------------------------
from typer.testing import CliRunner  # noqa: E402

from comfy_model.cli import app  # noqa: E402


@pytest.mark.parametrize("sub", ["run", "sheets"])
def test_bakeoff_commands_registered(sub):
    assert CliRunner().invoke(app, ["bakeoff", sub, "--help"]).exit_code == 0


def test_face_output_prefix_carries_the_face_mark(tmp_path):
    c = FakeClient()
    bk.run_bakeoff(["z_image"], c, tmp_path, limit=1)
    prefixes = {n["inputs"]["filename_prefix"] for n in c.queued[0].values() if n["class_type"] == "SaveImage"}
    assert prefixes == {"bakeoff/z_image/mirror-selfie-home_01", "bakeoff/z_image/mirror-selfie-home_01_face"}
    # ComfyUI appends _00001_.png, which is how the runner tells the two files apart
    assert bk._FACE_MARK in "mirror-selfie-home_01_face_00001_.png"
    assert bk._FACE_MARK not in "mirror-selfie-home_01_00001_.png"


def test_face_crops_are_shown_unscaled(tmp_path):
    p = tmp_path / "c.png"
    Image.new("RGB", (100, 200), "white").save(p)
    tile = bk._tile(p, (400, 400), "A", "no face", scale=False)
    assert tile.size == (400, 400)
    assert tile.getpixel((99, 199)) == (255, 255, 255)  # crop corner at original size
    assert tile.getpixel((150, 300)) != (255, 255, 255)  # not stretched to fill


def test_hidream_detailer_forces_a_size_divisible_by_32():
    # HiDream-O1 has no patch padding: any other crop size crashes its transformer.
    g = load_graph("hidream_o1")
    hook = g[_detailer_id(g)]["inputs"]["detailer_hook"]
    assert g[hook[0]]["class_type"] == "CoreMLDetailerHookProvider"
    w, h = (int(x) for x in g[hook[0]]["inputs"]["mode"].split("x"))
    assert w % 32 == 0 and h % 32 == 0


def test_repeated_errors_stop_the_run(tmp_path):
    c = FakeClient(fail=ComfyError("cuda oom"))
    report = bk.run_bakeoff(["z_image", "z_image_turbo"], c, tmp_path)
    assert len(c.queued) == bk.MAX_CONSECUTIVE_FAILURES
    assert report.aborted and "cm pod status" in report.aborted


def test_one_error_does_not_stop_the_run(tmp_path):
    class Flaky(FakeClient):
        def queue(self, wf):
            self.queued.append(wf)
            if len(self.queued) == 1:
                raise ComfyError("hiccup")
            return "p"

    report = bk.run_bakeoff(["z_image"], Flaky(), tmp_path, limit=4)
    assert len(report.failed) == 1 and len(report.done) == 3 and report.aborted is None


def test_wider_frames_are_letterboxed_not_stretched(tmp_path):
    p = tmp_path / "f.png"
    Image.new("RGB", (700, 900), "white").save(p)  # 7:9, narrower than the 4:5 cell
    tile = bk._tile(p, (512, 640), "A", "no frame")
    assert tile.size == (512, 640)
    assert tile.getpixel((2, 320)) != (255, 255, 255)


def test_sheets_keep_full_chroma_for_skin_detail(tmp_path):
    _run_all(tmp_path)
    with Image.open(bk.make_sheets(tmp_path) / "mirror-selfie-home_faces.jpg") as im:
        assert im.layer[0][1:3] == (1, 1)


@pytest.mark.parametrize("name", NAMES)
def test_face_detailer_crops_tightly(name):
    # A 3x crop of a selfie face is the whole frame, which FaceDetailer then shrinks.
    g = load_graph(name)
    assert g[_detailer_id(g)]["inputs"]["bbox_crop_factor"] == 1.6


@pytest.mark.parametrize("name", ["z_image", "z_image_turbo"])
def test_z_image_face_pass_uses_euler(name):
    # res_multistep leaves the partially denoised face scaly.
    g = load_graph(name)
    assert g[_detailer_id(g)]["inputs"]["sampler_name"] == "euler"
