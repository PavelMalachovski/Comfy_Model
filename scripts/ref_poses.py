"""Roxana in the poses of reference photos: hero-opt Qwen + ohwxroxana_v5, DWPose skeleton -> InstantX ControlNet.
Only the skeleton is taken from a reference (face keypoints off); faces, clothes and places come from the prompt.
The output keeps the reference's aspect ratio (~1 MP). A scene without `ref` renders from the prompt alone.

Spec (YAML): tier, count, scenes [{id, ref?, crop? [x0,y0,x1,y1 fractions], size? [w,h] (no ref), appearance?, seed, prompt}].
`appearance` replaces the profile's (face) description for frames with no face in them, e.g. feet only.
  python scripts/ref_poses.py scenes/x_refs20.yaml --out out/dev/x-refs20 --url http://127.0.0.1:8192 [--only id,id]
Files: <out>/<id>_<n>.png and <out>/<id>_skeleton.png.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from comfy_model.comfy_client import ComfyClient  # noqa: E402
from comfy_model.profile import load_profile  # noqa: E402
from comfy_model.safety import check_prompt  # noqa: E402
from comfy_model.workflow import render  # noqa: E402
from video_keys import object_inputs  # noqa: E402

GRAPH = ROOT / "workflows/qwen-mac-hero-opt-v5-40/photo.json"
PROFILE = ROOT / "character/profile_phone_40.yaml"
LORA, LORA_S = "ohwxroxana_v5.safetensors", 0.8
AREA = 768 * 1344


def size_for(ratio: float) -> tuple[int, int]:
    w = int(math.sqrt(AREA * ratio)) // 16 * 16
    return w, int(w / ratio) // 16 * 16


def prep_ref(ref: Path, crop, out: Path) -> tuple[Path, int, int]:
    img = Image.open(ref).convert("RGB")
    if crop:
        W0, H0 = img.size
        img = img.crop((int(crop[0] * W0), int(crop[1] * H0), int(crop[2] * W0), int(crop[3] * H0)))
    w, h = size_for(img.width / img.height)
    dest = out / "_refs" / f"{ref.stem}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.resize((w, h), Image.LANCZOS).save(dest)
    return dest, w, h


def add_pose(c: ComfyClient, g: dict, upload: str) -> None:
    dw = {}
    for name, spec in object_inputs(c, "DWPreprocessor").items():
        if name == "image":
            continue
        opts = spec[0]
        dflt = spec[1].get("default") if len(spec) > 1 and isinstance(spec[1], dict) else None
        dw[name] = dflt if dflt is not None else (opts[0] if isinstance(opts, list) else None)
    dw.update(detect_hand="enable", detect_body="enable", detect_face="disable", resolution=1024)
    g["40"] = {"class_type": "LoadImage", "inputs": {"image": upload}}
    g["41"] = {"class_type": "DWPreprocessor", "inputs": {"image": ["40", 0], **dw}}
    g["44"] = {"class_type": "SaveImage", "inputs": {"images": ["41", 0], "filename_prefix": "cm/skeleton"}}
    g["42"] = {"class_type": "ControlNetLoader",
               "inputs": {"control_net_name": "Qwen-Image-InstantX-ControlNet-Union.safetensors"}}
    g["43"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
        "positive": ["5", 0], "negative": ["6", 0], "control_net": ["42", 0], "image": ["41", 0],
        "strength": 0.9, "start_percent": 0.0, "end_percent": 0.6, "vae": ["4", 0]}}
    g["8"]["inputs"]["positive"] = ["43", 0]
    g["8"]["inputs"]["negative"] = ["43", 1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--only")
    a = ap.parse_args()
    spec = yaml.safe_load(Path(a.spec).read_text())
    tier, count = spec["tier"], int(spec.get("count", 3))
    prof = load_profile(PROFILE)
    tpl = json.loads(GRAPH.read_text())
    def prompt_for(s: dict) -> str:
        p = dataclasses.replace(prof, appearance=s["appearance"]) if s.get("appearance") else prof
        return p.photo_prompt(s["prompt"], use_trigger=True)
    for s in spec["scenes"]:
        bad = check_prompt(prompt_for(s), tier)
        assert not bad, (s["id"], bad)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with ComfyClient(a.url) as c:
        for s in spec["scenes"]:
            if a.only and s["id"] not in a.only.split(","):
                continue
            upload, (w, h) = None, s.get("size", (768, 1344))
            if s.get("ref"):
                p, w, h = prep_ref(ROOT / s["ref"], s.get("crop"), out)
                upload = c.upload_image(p, name=f"xref-{p.name}")
            for n in range(1, count + 1):
                dest = out / f"{s['id']}_{n}.png"
                if dest.exists():
                    print("skip", dest.name); continue
                g = render(tpl, {"prompt": prompt_for(s),
                                 "seed": int(s["seed"]) + n - 1, "filename_prefix": f"cm/xref-{s['id']}",
                                 "width": w, "height": h, "lora_name": LORA, "lora_strength": LORA_S})
                if upload:
                    add_pose(c, g, upload)
                entry = c.wait(c.queue(g), timeout_s=3600)
                outs = c.outputs(entry)
                if upload and n == 1:
                    sk = [f for f in outs if "skeleton" in f.filename]
                    if sk:
                        c.download(sk[-1], out / f"{s['id']}_skeleton.png")
                c.download([f for f in outs if "skeleton" not in f.filename][-1], dest)
                print("saved", dest, flush=True)


if __name__ == "__main__":
    main()
