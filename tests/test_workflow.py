from pathlib import Path

import pytest

from comfy_model.workflow import (
    KINDS,
    PLACEHOLDERS,
    TemplateError,
    load_manifest,
    load_template,
    model_files,
    placeholders,
    render,
)

COMFY_MODEL_DIRS = {
    "checkpoints", "diffusion_models", "text_encoders", "vae", "loras",
    "upscale_models", "ultralytics/bbox",
}


def sample_values(kind: str) -> dict:
    vals = {
        "prompt": "a woman at her desk", "negative": "blurry", "seed": 42,
        "width": 896, "height": 1120, "batch_size": 2, "length": 121,
        "filename_prefix": "x/y", "ref_image": "ref.png", "image": "start.png",
        "lora_name": "greta.safetensors", "lora_strength": 0.9,
    }
    return {k: vals[k] for k in PLACEHOLDERS[kind]}


def test_placeholder_sets():
    assert PLACEHOLDERS == {
        "face": {"prompt", "seed", "width", "height", "batch_size", "filename_prefix"},
        "dataset": {"prompt", "seed", "ref_image", "filename_prefix"},
        "photo": {"prompt", "seed", "width", "height", "lora_name", "lora_strength", "filename_prefix"},
        "video": {"prompt", "negative", "seed", "image", "width", "height", "length", "filename_prefix"},
    }
    assert set(KINDS) == set(PLACEHOLDERS)


@pytest.mark.parametrize("kind", sorted(PLACEHOLDERS))
def test_each_template_has_exact_placeholders(kind):
    assert placeholders(load_template(kind)) == PLACEHOLDERS[kind]


def test_load_template_unknown_kind():
    with pytest.raises(TemplateError, match="nope"):
        load_template("nope")


def test_render_keeps_types():
    t = load_template("face")
    out = render(t, sample_values("face"))
    seeds = [n["inputs"]["seed"] for n in out.values() if "seed" in n["inputs"]]
    assert seeds == [42] and isinstance(seeds[0], int)
    widths = [n["inputs"]["width"] for n in out.values() if "width" in n["inputs"]]
    assert widths == [896]
    assert placeholders(out) == set()


def test_render_does_not_mutate_template():
    t = load_template("photo")
    render(t, sample_values("photo"))
    assert placeholders(t) == PLACEHOLDERS["photo"]


def test_render_unfilled_raises():
    vals = sample_values("face")
    del vals["seed"]
    with pytest.raises(TemplateError, match="seed"):
        render(load_template("face"), vals)


def test_render_unused_value_raises():
    vals = sample_values("face") | {"lora_name": "x.safetensors"}
    with pytest.raises(TemplateError, match="lora_name"):
        render(load_template("face"), vals)


def test_render_only_whole_string_placeholders():
    t = {"1": {"class_type": "X", "inputs": {"a": "{{a}}", "b": "pre {{a}}", "c": ["1", 0]}}}
    out = render(t, {"a": 3})
    assert out["1"]["inputs"] == {"a": 3, "b": "pre {{a}}", "c": ["1", 0]}


@pytest.mark.parametrize("kind", sorted(PLACEHOLDERS))
def test_graph_links_valid(kind):
    t = load_template(kind)
    assert t, "empty template"
    for nid, node in t.items():
        assert isinstance(node.get("class_type"), str) and node["class_type"], nid
        assert isinstance(node.get("inputs"), dict), nid
        for key, val in node["inputs"].items():
            if isinstance(val, list):
                assert len(val) == 2 and isinstance(val[0], str) and isinstance(val[1], int), (nid, key)
                assert val[0] in t, f"node {nid}.{key} links to missing node {val[0]}"
                assert val[0] != nid, f"node {nid}.{key} links to itself"


@pytest.mark.parametrize("kind", sorted(PLACEHOLDERS))
def test_graph_has_output_node(kind):
    classes = {n["class_type"] for n in load_template(kind).values()}
    assert classes & {"SaveImage", "SaveVideo"}


def _nodes(t: dict, class_type: str) -> list[dict]:
    return [n["inputs"] for n in t.values() if n["class_type"] == class_type]


def test_face_graph_settings():
    t = load_template("face")
    (ks,) = _nodes(t, "KSampler")
    assert (ks["sampler_name"], ks["scheduler"], ks["steps"], ks["cfg"], ks["denoise"]) == ("euler", "beta", 28, 1.0, 1.0)
    assert [g["guidance"] for g in _nodes(t, "FluxGuidance")] == [2.5]
    assert _nodes(t, "CheckpointLoaderSimple")[0]["ckpt_name"] == "flux1-dev-fp8.safetensors"
    (lat,) = _nodes(t, "EmptySD3LatentImage")
    assert (lat["width"], lat["height"], lat["batch_size"]) == ("{{width}}", "{{height}}", "{{batch_size}}")


def test_dataset_graph_settings():
    t = load_template("dataset")
    (ks,) = _nodes(t, "KSampler")
    assert (ks["sampler_name"], ks["scheduler"], ks["steps"], ks["cfg"], ks["denoise"]) == ("euler", "simple", 24, 1.0, 1.0)
    assert [g["guidance"] for g in _nodes(t, "FluxGuidance")] == [2.5]
    (clip,) = _nodes(t, "DualCLIPLoader")
    assert (clip["clip_name1"], clip["clip_name2"], clip["type"]) == (
        "clip_l.safetensors", "t5xxl_fp8_e4m3fn_scaled.safetensors", "flux")
    for ct in ("FluxKontextImageScale", "VAEEncode", "ReferenceLatent", "VAEDecode", "SaveImage"):
        assert _nodes(t, ct), ct


def test_photo_graph_settings():
    t = load_template("photo")
    (ks,) = _nodes(t, "KSampler")
    assert (ks["sampler_name"], ks["scheduler"], ks["steps"], ks["cfg"]) == ("euler", "beta", 28, 1.0)
    (lora,) = _nodes(t, "LoraLoaderModelOnly")
    assert (lora["lora_name"], lora["strength_model"]) == ("{{lora_name}}", "{{lora_strength}}")
    (fd,) = _nodes(t, "FaceDetailer")
    assert fd["denoise"] == 0.35
    (det,) = _nodes(t, "UltralyticsDetectorProvider")
    assert det["model_name"] == "bbox/face_yolov8m.pt"
    assert _nodes(t, "UpscaleModelLoader")[0]["model_name"] == "RealESRGAN_x4plus.pth"
    assert _nodes(t, "ImageScaleBy")[0]["scale_by"] == 0.5
    # KSampler must sample with the LoRA-patched model
    lora_id = next(k for k, n in t.items() if n["class_type"] == "LoraLoaderModelOnly")
    assert ks["model"][0] == lora_id


def test_video_graph_settings():
    t = load_template("video")
    (ks,) = _nodes(t, "KSampler")
    assert (ks["sampler_name"], ks["scheduler"], ks["steps"], ks["cfg"]) == ("uni_pc", "simple", 30, 5)
    assert _nodes(t, "ModelSamplingSD3")[0]["shift"] == 8
    assert _nodes(t, "CreateVideo")[0]["fps"] == 24
    assert _nodes(t, "SaveVideo")[0]["format"] == "mp4"
    assert _nodes(t, "CLIPLoader")[0]["type"] == "wan"


def test_model_files_literal_only():
    assert model_files(load_template("photo")) == {
        "flux1-dev-fp8.safetensors", "bbox/face_yolov8m.pt", "RealESRGAN_x4plus.pth",
    }
    assert model_files(load_template("video")) == {
        "wan2.2_ti2v_5B_fp16.safetensors", "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan2.2_vae.safetensors",
    }


@pytest.mark.parametrize("kind", sorted(PLACEHOLDERS))
def test_every_model_file_in_manifest(kind):
    files = {m.file for m in load_manifest()}
    used = {v.split("/")[-1] for v in model_files(load_template(kind))}
    assert used, kind
    assert used <= files, used - files


def test_manifest_dests_are_comfy_folders():
    manifest = load_manifest()
    assert manifest
    for m in manifest:
        assert m.dest in COMFY_MODEL_DIRS, m


def test_manifest_urls():
    by_file = {m.file: m for m in load_manifest()}
    assert len(by_file) == len(load_manifest()), "duplicate file in manifest"
    assert by_file["flux1-dev-fp8.safetensors"].url == (
        "https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors")
    assert by_file["ae.safetensors"].url == (
        "https://huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors")
    assert by_file["RealESRGAN_x4plus.pth"].url == (
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth")
    assert by_file["face_yolov8m.pt"].dest == "ultralytics/bbox"
    # the bbox detector's template value "bbox/face_yolov8m.pt" resolves under ultralytics/
    assert by_file["face_yolov8m.pt"].url.endswith("/Bingsu/adetailer/resolve/main/face_yolov8m.pt")


def test_manifest_every_template_model_has_one_entry():
    all_used = set()
    for kind in KINDS:
        all_used |= {v.split("/")[-1] for v in model_files(load_template(kind))}
    assert all_used == {m.file for m in load_manifest()}


def test_manifest_rejects_entry_without_source(tmp_path: Path):
    p = tmp_path / "m.yaml"
    p.write_text("models:\n  - {file: a.safetensors, dest: vae}\n")
    with pytest.raises(TemplateError, match="a.safetensors"):
        load_manifest(p)
