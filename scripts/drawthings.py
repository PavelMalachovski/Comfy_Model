"""Local Mac tests through the Draw Things HTTP API (A1111-compatible, default port 7860).

    uv run python scripts/drawthings.py face  [--n 10]
    uv run python scripts/drawthings.py scene --ref out/dev/mac-test/face/face-03.png [--ids a,b,c]

Prompts are assembled exactly like `cm` does (appearance + scene + style_suffix) and
run through the same tier safety check before anything is sent.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import random
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from comfy_model.profile import load_profile
from comfy_model.safety import check_prompt
from comfy_model.scenes import load_scenes

API = "http://127.0.0.1:7860"
DEV = "flux_1_dev_q8p.ckpt"
KONTEXT = "flux_1_kontext_dev_q8p.ckpt"
MODELS = {"dev": DEV, "krea": "flux_1_krea_dev_q8p.ckpt"}
# Draw Things snaps sizes to multiples of 64 (896x1120 -> 896x1088), so use snapped sizes.
SIZES = {"4:5": (896, 1088), "9:16": (768, 1344), "1:1": (1024, 1024)}
DEFAULT_SCENES = [
    "boardroom-head-of-table",
    "penthouse-skyline-gown",
    "yacht-deck-white-linen",
    "glass-desk-office",
    "rooftop-bar-evening",
    "home-armchair-low-angle",
]
# Ad-hoc test scenes not (yet) in scenes/instagram.yaml; same tier check applies.
EXTRA = {
    "home-armchair-low-angle": SimpleNamespace(aspect="4:5", prompt=(
        "dramatic worm's-eye view shot from the floor, camera pointing steeply upward at her, "
        "she sits in a deep black leather armchair in her modern living room at home, legs crossed toward "
        "the camera, black silk blouse and tailored black trousers, warm evening lamp light, ceiling visible "
        "behind her, she looks straight down into the lens with open eyes and a cold confident gaze")),
}


def post(path: str, payload: dict) -> list[bytes]:
    req = urllib.request.Request(
        API + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=1800) as r:
        body = json.load(r)
    return [base64.b64decode(i) for i in body.get("images", [])]


def guard(prompt: str) -> None:
    problems = check_prompt(prompt, "instagram")
    if problems:
        sys.exit("refusing to send prompt: " + "; ".join(problems))


def face(args: argparse.Namespace) -> None:
    profile = load_profile()
    scene = next(s for s in load_scenes(Path("scenes/face.yaml"), "face") if s.id == "face-window-light")
    prompt = profile.photo_prompt(scene.prompt, use_trigger=False)
    guard(prompt)
    out = Path("out/dev/mac-test/face")
    out.mkdir(parents=True, exist_ok=True)
    w, h = SIZES["4:5"]
    log = out / "seeds.jsonl"
    for i in range(args.n):
        seed = random.randrange(2**32)
        steps = random.choice([20, 22, 25])
        guidance = random.choice([3.0, 3.5])
        print(f"[{i + 1}/{args.n}] seed={seed} steps={steps} guidance={guidance}", flush=True)
        imgs = post("/sdapi/v1/txt2img", {
            "prompt": prompt, "negative_prompt": "", "model": MODELS[args.model], "width": w, "height": h,
            "steps": steps, "guidance_scale": guidance, "guidance_embed": guidance, "seed": seed, "batch_size": 1,
        })
        name = f"face-{args.prefix}{i + 1:02d}.png"
        (out / name).write_bytes(imgs[0])
        with log.open("a") as f:
            f.write(json.dumps({"file": name, "model": MODELS[args.model], "seed": seed, "steps": steps, "guidance": guidance,
                                "prompt": prompt}) + "\n")


def fit_ref(path: str, w: int, h: int) -> str:
    """Kontext needs init_images at the exact target size: letterbox the ref (no face crop)."""
    from PIL import Image, ImageOps
    im = Image.open(path).convert("RGB")
    canvas = ImageOps.pad(im, (w, h), color=(20, 20, 20))
    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def scene(args: argparse.Namespace) -> None:
    scenes = {s.id: s for s in load_scenes(Path("scenes/instagram.yaml"), "photo")} | EXTRA
    ids = args.ids.split(",") if args.ids else DEFAULT_SCENES
    out = Path("out/dev/mac-test/kontext")
    out.mkdir(parents=True, exist_ok=True)
    for sid in ids:
        s = scenes[sid]
        prompt = (f"Place this exact same woman in a new photo: {s.prompt}. Keep her face, facial "
                  f"features, age, skin texture, hair and identity exactly the same. "
                  f"{load_profile().style_suffix}")
        guard(prompt)
        w, h = SIZES[s.aspect]
        seed = random.randrange(2**32)
        print(f"{sid} {w}x{h} seed={seed}", flush=True)
        imgs = post("/sdapi/v1/img2img", {
            "prompt": prompt, "negative_prompt": "", "model": KONTEXT, "init_images": [fit_ref(args.ref, w, h)],
            "strength": 1.0, "width": w, "height": h, "steps": 25, "guidance_scale": 3.0, "guidance_embed": 3.0,
            "seed": seed, "batch_size": 1,
        })
        (out / f"{sid}.png").write_bytes(imgs[0])
        with (out / "seeds.jsonl").open("a") as f:
            f.write(json.dumps({"file": f"{sid}.png", "ref": args.ref, "seed": seed, "prompt": prompt}) + "\n")


def dataset(args: argparse.Namespace) -> None:
    """scenes/dataset.yaml Kontext edits of the ref -> out dir + manifest.jsonl for `cm lora prepare`."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    done = {p.name for p in out.glob("*.png")}
    scenes = load_scenes(Path("scenes/dataset.yaml"), "dataset")
    for i, s in enumerate(scenes, 1):
        name = f"{s.id}.png"
        if name in done:  # resumable
            continue
        guard(s.prompt)
        w, h = SIZES[s.aspect]
        seed = random.randrange(2**32)
        print(f"[{i}/{len(scenes)}] {s.id} {w}x{h} seed={seed}", flush=True)
        imgs = post("/sdapi/v1/img2img", {
            "prompt": s.prompt, "negative_prompt": "", "model": KONTEXT,
            "init_images": [fit_ref(args.ref, w, h)], "strength": 1.0, "width": w, "height": h,
            "steps": 25, "guidance_scale": 3.0, "guidance_embed": 3.0, "seed": seed, "batch_size": 1,
        })
        (out / name).write_bytes(imgs[0])
        with (out / "manifest.jsonl").open("a") as f:
            f.write(json.dumps({"file": name, "scene": s.id, "seed": seed, "prompt": s.prompt}) + "\n")


SELFIE_PROMPT = (
    "amateur iPhone mirror selfie of a 40-year-old woman with long sleek dark brunette hair in a high "
    "ponytail, dark brown eyes, defined cheekbones, holding a white phone in front of the mirror, dim "
    "bedroom at night, warm bedside lamp, black silk blouse, soft matte red lips, natural skin with "
    "visible pores and fine lines around the eyes, flyaway hairs, casual unposed, cold confident gaze, "
    "slight grain, no retouching"
)


SELFIE_OLDER = (
    "amateur iPhone mirror selfie of a 42-year-old woman, clearly in her forties, mature face with fine "
    "lines at the outer corners of her eyes, forehead lines, soft nasolabial folds and slightly tired under-eyes, long sleek dark "
    "brunette hair in a high ponytail, dark brown eyes, defined cheekbones, half-body shot with the whole "
    "face visible, one hand holding a phone in a plain black case with no logos low at chest height to the "
    "side, standing a few steps back from the mirror, dim bedroom at night, warm bedside lamp, black silk "
    "blouse, soft matte red lips, oxblood nails, natural uneven skin with visible pores, flyaway hairs, "
    "casual unposed, cold confident gaze, slight grain, no retouching"
)
SELFIE_PROMPTS = {"base": SELFIE_PROMPT, "older": SELFIE_OLDER}


def to_b64(im) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def finish(png: bytes, dest: Path, seed: int) -> None:
    """Luminance film grain + JPEG q85: phone-photo finish (PIL only)."""
    from PIL import Image, ImageChops
    im = Image.open(io.BytesIO(png)).convert("RGB")
    random.seed(seed)
    grain = Image.effect_noise(im.size, 4.0).convert("RGB")  # gray noise centred on 128
    ImageChops.add(im, grain, scale=1.0, offset=-128).save(dest, "JPEG", quality=85)


def selfie(args: argparse.Namespace) -> None:
    from PIL import Image
    prompt = SELFIE_PROMPTS[args.prompt]
    guard(prompt)
    out = Path("out/dev/mac-test/selfie")
    out.mkdir(parents=True, exist_ok=True)
    w, h = 1024, 1280
    for i in range(args.n):
        seed = random.randrange(2**32)
        print(f"[{i + 1}/{args.n}] base seed={seed}", flush=True)
        base = post("/sdapi/v1/txt2img", {
            "prompt": prompt, "negative_prompt": "", "model": MODELS["krea"], "width": w,
            "height": h, "steps": 28, "guidance_scale": args.guidance, "guidance_embed": args.guidance,
            "seed": seed, "batch_size": 1,
        })[0]
        name = f"selfie-{args.prompt}-{i + 1:02d}"
        (out / f"{name}-base.png").write_bytes(base)
        # Refine pass: 1.5x Lanczos upscale, low-strength img2img to redraw pores, lashes, hair.
        W, H = 1536, 1920
        big = Image.open(io.BytesIO(base)).convert("RGB").resize((W, H), Image.LANCZOS)
        print(f"[{i + 1}/{args.n}] refine {W}x{H}", flush=True)
        ref = post("/sdapi/v1/img2img", {
            "prompt": prompt, "negative_prompt": "", "model": MODELS["krea"],
            "init_images": [to_b64(big)], "strength": args.refine, "width": W, "height": H, "steps": 28,
            "guidance_scale": args.guidance, "guidance_embed": args.guidance, "seed": seed, "batch_size": 1,
        })[0]
        finish(ref, out / f"{name}.jpg", seed)
        with (out / "seeds.jsonl").open("a") as f:
            f.write(json.dumps({"file": f"{name}.jpg", "seed": seed, "guidance": args.guidance,
                                "prompt": prompt}) + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("face")
    f.add_argument("--n", type=int, default=10)
    f.add_argument("--model", choices=sorted(MODELS), default="dev")
    f.add_argument("--prefix", default="", help="file name prefix, e.g. krea-")
    s = sub.add_parser("scene")
    s.add_argument("--ref", required=True)
    s.add_argument("--ids")
    d = sub.add_parser("dataset")
    d.add_argument("--ref", required=True)
    d.add_argument("--out", default="out/dev/mac-test/dataset")
    sf = sub.add_parser("selfie")
    sf.add_argument("--n", type=int, default=4)
    sf.add_argument("--guidance", type=float, default=2.2)
    sf.add_argument("--prompt", choices=sorted(SELFIE_PROMPTS), default="base")
    sf.add_argument("--refine", type=float, default=0.3, help="img2img strength of the refine pass")
    a = p.parse_args()
    {"face": face, "scene": scene, "dataset": dataset, "selfie": selfie}[a.cmd](a)


if __name__ == "__main__":
    main()
