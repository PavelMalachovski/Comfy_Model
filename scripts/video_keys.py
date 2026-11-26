"""Long clips (12-14 s) from keyframes: Qwen keyframes -> Wan 2.2 first-last-frame segments -> one mp4.

  .venv/bin/python scripts/video_keys.py keys  scenes/video_ig_long.yaml --out out/dev/video-ig-long --url http://127.0.0.1:8190
  .venv/bin/python scripts/video_keys.py video scenes/video_ig_long.yaml --out out/dev/video-ig-long --url http://127.0.0.1:8190 [--set 1] [--only id,id]

keys:  for every video and every variant (seed), the `base` key is rendered with the hero-opt Qwen graph + LoRA
       (optionally posed by a reference: DWPose skeleton -> InstantX ControlNet; only the skeleton is used, never the
       person in the reference). Every other key is a Qwen-Image-Edit-2511 edit of the base key, or of key k<from:>
       when it has `from: <index>` (an earlier key in the list). A key with its own `prompt:` is rendered like
       the base (Qwen + LoRA, same seed): use it when the face must stay exact (Qwen-Edit has no LoRA).
       Files: <out>/<id>/set<N>/k<i>.png (+ skeleton.png). Review them, then:
video: per video, Wan 2.2 I2V 14B + Lightning 4 steps, segment i goes k<i> -> k<i+1> (WanFirstLastFrameToVideo);
       with a single key the segments chain (image-to-video from k0, then from the previous segment's last frame);
       segments are joined (the shared frame dropped once), FILM x2 -> 32 fps. Out: <out>/<id>/<id>_set<N>.mp4.
facefix: re-draw the faces of already rendered Qwen-Edit keys with the LoRA (Qwen-Edit has no persona LoRA and
       drifts the face; FaceDetailer at denoise 0.6 brings her face back, pose and angle stay).
Every prompt is checked with safety.check_prompt for the video's tier. Existing files are skipped (safe to re-run).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from comfy_model.comfy_client import ComfyClient  # noqa: E402
from comfy_model.profile import load_profile  # noqa: E402
from comfy_model.safety import check_prompt  # noqa: E402
from comfy_model.workflow import render  # noqa: E402

PHOTO_GRAPH = ROOT / "workflows/qwen-mac-hero-opt-v5-40/photo.json"
EDIT_GRAPH = ROOT / "workflows/qwen-mac-edit/edit.json"
PROFILE = ROOT / "character/profile_phone_40.yaml"
LORA, LORA_S = "ohwxroxana_v5.safetensors", 0.8
W, H = 768, 1344          # Qwen 9:16
VW, VH = 704, 1280        # Wan 9:16
NEG_FANVUE = ("child, teen, underage, deformed, extra limbs, extra fingers, blurry, low quality, distorted face, "
              "plastic skin, text, watermark, another person")


def load_spec(path: Path) -> list[dict]:
    spec = yaml.safe_load(path.read_text())
    vids = spec["videos"]
    problems = []
    for v in vids:
        tier = v["tier"]
        texts = [v["base"]["prompt"]] + [k.get("edit") or k["prompt"] for k in v["keys"] if k != "base"] + [s["prompt"] for s in v["segments"]]
        for t in texts:
            problems += [f"{v['id']}: {p}" for p in check_prompt(t, tier)]
        if len(v["keys"]) > 1 and len(v["segments"]) != len(v["keys"]) - 1:
            problems.append(f"{v['id']}: need len(keys)-1 segments (or a single key: chained image-to-video)")
        if sum(1 for k in v["keys"] if k == "base") != 1:
            problems.append(f"{v['id']}: exactly one key must be 'base'")
    if problems:
        raise SystemExit("prompt check failed:\n" + "\n".join(problems))
    return vids


def object_inputs(c: ComfyClient, node: str) -> dict:
    d = c._request("GET", f"/object_info/{node}").json()[node]["input"]
    return {**d.get("required", {}), **d.get("optional", {})}


def run(c: ComfyClient, graph: dict, dest: Path, pick: int = -1) -> Path:
    entry = c.wait(c.queue(graph), timeout_s=3 * 3600)
    outs = c.outputs(entry)
    return c.download(outs[pick], dest)


def pose_nodes(c: ComfyClient, g: dict, ref: Path, uploads: dict) -> None:
    """DWPose skeleton of the (9:16-padded) reference -> InstantX ControlNet on the first sampler only."""
    if ref not in uploads:
        padded = ROOT / "out/dev/.pose-ref-padded" / ref.name
        padded.parent.mkdir(parents=True, exist_ok=True)
        ImageOps.pad(Image.open(ref).convert("RGB"), (W, H), color=(255, 255, 255)).save(padded)
        uploads[ref] = c.upload_image(padded, name=f"poseref-{ref.stem}.png")
    dw = {}
    for name, spec in object_inputs(c, "DWPreprocessor").items():
        if name == "image":
            continue
        opts = spec[0]
        dflt = spec[1].get("default") if len(spec) > 1 and isinstance(spec[1], dict) else None
        dw[name] = dflt if dflt is not None else (opts[0] if isinstance(opts, list) else None)
    dw.update(detect_hand="enable", detect_body="enable", detect_face="disable", resolution=1024)
    g["40"] = {"class_type": "LoadImage", "inputs": {"image": uploads[ref]}}
    g["41"] = {"class_type": "DWPreprocessor", "inputs": {"image": ["40", 0], **dw}}
    g["44"] = {"class_type": "SaveImage", "inputs": {"images": ["41", 0], "filename_prefix": "cm/skeleton"}}
    g["42"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": "Qwen-Image-InstantX-ControlNet-Union.safetensors"}}
    g["43"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
        "positive": ["5", 0], "negative": ["6", 0], "control_net": ["42", 0], "image": ["41", 0],
        "strength": 0.9, "start_percent": 0.0, "end_percent": 0.6, "vae": ["4", 0]}}
    g["8"]["inputs"]["positive"] = ["43", 0]
    g["8"]["inputs"]["negative"] = ["43", 1]


def face_fix(c: ComfyClient, prof, photo_tpl: dict, img: Path, scene: str, seed: int, denoise: float) -> None:
    """Re-draw the face of an edited key with Qwen-Image + persona LoRA (FaceDetailer only), in place."""
    g = render(photo_tpl, {"prompt": prof.photo_prompt(scene, use_trigger=True), "seed": seed,
                           "filename_prefix": "cm/facefix", "width": W, "height": H,
                           "lora_name": LORA, "lora_strength": LORA_S})
    for nid in ("7", "8", "9", "10", "11", "12", "13", "23", "24"):
        g.pop(nid, None)
    g["50"] = {"class_type": "LoadImage", "inputs": {"image": c.upload_image(img, name=f"facefix-{img.parent.parent.name}-{img.parent.name}-{img.name}")}}
    g["21"]["inputs"].update(image=["50", 0], denoise=denoise)
    g["22"]["inputs"]["images"] = ["21", 0]
    run(c, g, img)


def edit_prompt(prof, text: str, edit_lora: float) -> str:
    return f"{prof.trigger}, {text}" if edit_lora and getattr(prof, "trigger", None) else text


def cmd_keys(c: ComfyClient, vids: list[dict], out: Path, variants: int, edit_lora: float = 0.0,
             facefix: float = 0.0) -> None:
    prof = load_profile(PROFILE)
    photo_tpl = json.loads(PHOTO_GRAPH.read_text())
    edit_tpl = json.loads(EDIT_GRAPH.read_text())
    uploads: dict = {}
    for v in vids:
        b = v["base"]
        bi = v["keys"].index("base")
        for n in range(1, variants + 1):
            d = out / v["id"] / f"set{n}"
            d.mkdir(parents=True, exist_ok=True)
            # 1) Qwen + LoRA renders: the base key and every key with its own `prompt` (same seed -> same look)
            for i, k in enumerate(v["keys"]):
                if k != "base" and "prompt" not in k:
                    continue
                dest = d / f"k{i}.png"
                if dest.exists():
                    continue
                kb = b if k == "base" else k
                g = render(photo_tpl, {"prompt": prof.photo_prompt(kb["prompt"], use_trigger=True),
                                       "seed": b["seed"] + 2 * (n - 1), "filename_prefix": f"cm/{v['id']}-k{i}",
                                       "width": W, "height": H, "lora_name": LORA, "lora_strength": LORA_S})
                if kb.get("pose"):
                    pose_nodes(c, g, ROOT / kb["pose"], uploads)
                entry = c.wait(c.queue(g), timeout_s=3 * 3600)
                outs = c.outputs(entry)
                for f in outs:
                    if "skeleton" in f.filename:
                        c.download(f, d / ("skeleton.png" if k == "base" else f"skeleton-k{i}.png"))
                c.download([f for f in outs if "skeleton" not in f.filename][-1], dest)
                print(f"{v['id']} set{n} k{i} (render)", flush=True)
            # 2) Qwen-Edit keys: from the base, or from key `from`
            base = d / f"k{bi}.png"
            up = None
            for i, k in enumerate(v["keys"]):
                dest = d / f"k{i}.png"
                if k == "base" or "edit" not in k or dest.exists():
                    continue
                if "from" in k:
                    src = c.upload_image(d / f"k{k['from']}.png", name=f"{v['id']}-set{n}-k{k['from']}.png")
                else:
                    up = up or c.upload_image(base, name=f"{v['id']}-set{n}-base.png")
                    src = up
                g = render(edit_tpl, {"image": src, "prompt": edit_prompt(prof, k["edit"], edit_lora),
                                      "seed": b["seed"] + 100 + i, "filename_prefix": f"cm/{v['id']}-k{i}"})
                if edit_lora:  # persona LoRA on Qwen-Edit too, so a visible face stays hers
                    g["31"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["30", 0], "lora_name": LORA,
                                                                              "strength_model": edit_lora}}
                    g["4"]["inputs"]["model"] = ["31", 0]
                run(c, g, dest)
                if facefix and k.get("face", True):
                    face_fix(c, prof, photo_tpl, dest, b["prompt"], b["seed"] + 200 + i, facefix)
                print(f"{v['id']} set{n} k{i} (edit{' + face fix' if facefix and k.get('face', True) else ''})", flush=True)


def cmd_facefix(c: ComfyClient, vids: list[dict], out: Path, denoise: float) -> None:
    """Apply the LoRA face fix to already rendered Qwen-Edit keys (original kept as k<i>_edit.png; runs once)."""
    prof = load_profile(PROFILE)
    photo_tpl = json.loads(PHOTO_GRAPH.read_text())
    for v in vids:
        for d in sorted((out / v["id"]).glob("set*")):
            for i, k in enumerate(v["keys"]):
                kp, keep = d / f"k{i}.png", d / f"k{i}_edit.png"
                if k == "base" or "edit" not in k or not k.get("face", True) or not kp.exists() or keep.exists():
                    continue
                keep.write_bytes(kp.read_bytes())
                face_fix(c, prof, photo_tpl, kp, v["base"]["prompt"], v["base"]["seed"] + 200 + i, denoise)
                print(f"{v['id']} {d.name} k{i} face fixed", flush=True)


def video_graph(keys: list[str], segs: list[dict], negative: str, prefix: str, seed: int) -> dict:
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "3": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", "strength_model": 1.0}},
        "4": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["2", 0], "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "strength_model": 1.0}},
        "5": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["3", 0], "shift": 5.0}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4", 0], "shift": 5.0}},
        "7": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan"}},
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["7", 0]}},
    }
    for i, k in enumerate(keys):
        g[f"10{i}"] = {"class_type": "LoadImage", "inputs": {"image": k}}
    prev = last = None
    last_n = 0
    for s, seg in enumerate(segs):
        p = f"2{s}"
        g[p + "0"] = {"class_type": "CLIPTextEncode", "inputs": {"text": seg["prompt"], "clip": ["7", 0]}}
        if len(keys) > 1:  # keyframe segment: k<s> -> k<s+1>
            g[p + "1"] = {"class_type": "WanFirstLastFrameToVideo", "inputs": {
                "positive": [p + "0", 0], "negative": ["9", 0], "vae": ["8", 0], "width": VW, "height": VH,
                "length": seg.get("frames", 105), "batch_size": 1, "start_image": [f"10{s}", 0], "end_image": [f"10{s + 1}", 0]}}
        else:  # single key: first segment starts from it, every next one from the last frame of the previous
            start = ["100", 0]
            if last is not None:
                g[p + "7"] = {"class_type": "ImageFromBatch", "inputs": {"image": last, "batch_index": last_n - 1, "length": 1}}
                start = [p + "7", 0]
            g[p + "1"] = {"class_type": "WanImageToVideo", "inputs": {
                "positive": [p + "0", 0], "negative": ["9", 0], "vae": ["8", 0], "width": VW, "height": VH,
                "length": seg.get("frames", 105), "batch_size": 1, "start_image": start}}
        common = {"steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                  "positive": [p + "1", 0], "negative": [p + "1", 1], "noise_seed": seed + s}
        g[p + "2"] = {"class_type": "KSamplerAdvanced", "inputs": {**common, "model": ["5", 0], "add_noise": "enable",
                      "latent_image": [p + "1", 2], "start_at_step": 0, "end_at_step": 2, "return_with_leftover_noise": "enable"}}
        g[p + "3"] = {"class_type": "KSamplerAdvanced", "inputs": {**common, "model": ["6", 0], "add_noise": "disable",
                      "latent_image": [p + "2", 0], "start_at_step": 2, "end_at_step": 10000, "return_with_leftover_noise": "disable"}}
        g[p + "4"] = {"class_type": "VAEDecode", "inputs": {"samples": [p + "3", 0], "vae": ["8", 0]}}
        frames = [p + "4", 0]
        last, last_n = frames, seg.get("frames", 105)
        if prev is not None:  # drop the first frame (= last frame of the previous segment)
            g[p + "5"] = {"class_type": "ImageFromBatch", "inputs": {"image": frames, "batch_index": 1, "length": 4095}}
            g[p + "6"] = {"class_type": "ImageBatch", "inputs": {"image1": prev, "image2": [p + "5", 0]}}
            frames = [p + "6", 0]
        prev = frames
    g["90"] = {"class_type": "FrameInterpolationModelLoader", "inputs": {"model_name": "film_net_fp16.safetensors"}}
    g["91"] = {"class_type": "FrameInterpolate", "inputs": {"interp_model": ["90", 0], "images": prev, "multiplier": 2}}
    g["92"] = {"class_type": "CreateVideo", "inputs": {"images": ["91", 0], "fps": 32}}
    g["93"] = {"class_type": "SaveVideo", "inputs": {"video": ["92", 0], "filename_prefix": prefix, "format": "mp4", "codec": "h264"}}
    return g


def cmd_video(c: ComfyClient, vids: list[dict], out: Path, sets: list[int]) -> None:
    prof = load_profile(PROFILE)
    for v in vids:
        neg = NEG_FANVUE if v["tier"] == "fanvue" else prof.video_negative
        for n in sets:
            d = out / v["id"] / f"set{n}"
            dest = out / v["id"] / f"{v['id']}_set{n}.mp4"
            if dest.exists():
                print("skip", dest); continue
            keys = [d / f"k{i}.png" for i in range(len(v["keys"]))]
            missing = [str(k) for k in keys if not k.exists()]
            if missing:
                print(f"{v['id']} set{n}: missing keys {missing}"); continue
            names = [c.upload_image(k, name=f"{v['id']}-set{n}-{k.name}") for k in keys]
            run(c, video_graph(names, v["segments"], neg, f"cm/{v['id']}", v["base"]["seed"]), dest)
            print(f"{v['id']} set{n} -> {dest}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["keys", "facefix", "video"])
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8190")
    ap.add_argument("--variants", type=int, default=2)
    ap.add_argument("--set", default="1", help="comma list of keyframe sets to animate")
    ap.add_argument("--only", default="", help="comma list of video ids")
    ap.add_argument("--face-fix", type=float, default=0.0,
                    help="re-draw faces of Qwen-Edit keys with the LoRA (FaceDetailer denoise, e.g. 0.55; 0 = off; skip a key with face: false)")
    ap.add_argument("--edit-lora", type=float, default=0.0, help="persona LoRA strength on Qwen-Edit keys (0 = off)")
    a = ap.parse_args()
    vids = load_spec(a.spec)
    if a.only:
        vids = [v for v in vids if v["id"] in a.only.split(",")]
    with ComfyClient(a.url) as c:
        if a.cmd == "keys":
            cmd_keys(c, vids, a.out, a.variants, a.edit_lora, a.face_fix)
        elif a.cmd == "facefix":
            cmd_facefix(c, vids, a.out, a.face_fix or 0.6)
        else:
            cmd_video(c, vids, a.out, [int(x) for x in a.set.split(",")])


if __name__ == "__main__":
    main()
