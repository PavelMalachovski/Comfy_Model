"""Masked SDXL repair pass for finished frames (Fanvue anatomy and hand fixes). Built-in ComfyUI nodes only.

For each fix in the spec: crop the box plus a context margin, scale the crop to ~1024 px, run SDXL img2img with a
latent noise mask over the box only, scale back and paste with a feathered edge. Several fixes on one image are
chained (each works on the previous result). The original stays untouched; the result goes to <out>/<stem>_fixed.png.

Spec (YAML):
  checkpoint: RealVisXL_V5.0_fp16.safetensors      # file in models/checkpoints on the instance
  negative: ...                                     # optional
  fixes:
  - image: out/dev/fanvue-bed-body-v2/m06-rear-all-fours_01.png
    box: [0.30, 0.55, 0.70, 0.85]                   # x0, y0, x1, y1 as fractions of width/height
    prompt: close-up of natural adult vulva ...
    denoise: 0.5                                    # optional, default 0.5
    seed: 1                                         # optional

  python scripts/inpaint_fix.py scenes/fanvue_inpaint.yaml --out out/dev/fanvue-inpaint --url http://127.0.0.1:8192
"""
import argparse
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, "src")
from comfy_model.comfy_client import ComfyClient  # noqa: E402
from comfy_model.safety import check_prompt  # noqa: E402

NEG = ("child, teen, underage, young looking, deformed anatomy, extra limbs, fused fingers, blurry, low quality, "
       "plastic skin, cartoon, 3d render, text, watermark, sex toy")
MARGIN = 0.6     # context around the box, as a fraction of the box size on each side
TARGET = 1024    # long side of the crop sent to SDXL
FEATHER = 24     # px of the paste-back blend, in crop pixels after scaling back


def crop_box(img, box):
    w, h = img.size
    x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
    mx, my = (x1 - x0) * MARGIN, (y1 - y0) * MARGIN
    c = (max(0, int(x0 - mx)), max(0, int(y0 - my)), min(w, int(x1 + mx)), min(h, int(y1 + my)))
    inner = (int(x0) - c[0], int(y0) - c[1], int(x1) - c[0], int(y1) - c[1])
    return c, inner


def graph(ckpt, crop_name, mask_name, prompt, negative, denoise, seed, prefix):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": negative}},
        "4": {"class_type": "LoadImage", "inputs": {"image": crop_name}},
        "5": {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}},
        "6": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SetLatentNoiseMask", "inputs": {"samples": ["6", 0], "mask": ["5", 0]}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
              "latent_image": ["7", 0], "seed": seed, "steps": 30, "cfg": 5.0, "sampler_name": "dpmpp_2m",
              "scheduler": "karras", "denoise": denoise}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": prefix}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--only", help="comma-separated image stems")
    a = ap.parse_args()
    spec = yaml.safe_load(Path(a.spec).read_text())
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_work"; tmp.mkdir(exist_ok=True)
    negative = spec.get("negative", NEG)
    for f in spec["fixes"]:
        bad = check_prompt(f["prompt"], "fanvue")
        assert not bad, (f["image"], bad)
    by_img = {}
    for f in spec["fixes"]:
        by_img.setdefault(f["image"], []).append(f)
    with ComfyClient(a.url) as c:
        for src, fixes in by_img.items():
            src = Path(src); stem = src.stem
            if a.only and stem not in a.only.split(","):
                continue
            dest = out / f"{stem}_fixed.png"
            if dest.exists():
                print("skip", dest.name); continue
            img = Image.open(src).convert("RGB")
            for n, f in enumerate(fixes, 1):
                (cx0, cy0, cx1, cy1), inner = crop_box(img, f["box"])
                crop = img.crop((cx0, cy0, cx1, cy1))
                s = TARGET / max(crop.size)
                size = (int(crop.width * s) // 8 * 8, int(crop.height * s) // 8 * 8)
                crop_up = crop.resize(size, Image.LANCZOS)
                mask = Image.new("L", size, 0)
                ImageDraw.Draw(mask).rectangle([int(v * s) for v in inner], fill=255)
                mask = mask.filter(ImageFilter.GaussianBlur(8))
                cp, mp = tmp / f"{stem}_{n}_crop.png", tmp / f"{stem}_{n}_mask.png"
                crop_up.save(cp); Image.merge("RGB", [mask] * 3).save(mp)
                cn, mn = c.upload_image(cp, name=cp.name), c.upload_image(mp, name=mp.name)
                g = graph(spec["checkpoint"], cn, mn, f["prompt"], negative, float(f.get("denoise", 0.5)),
                          int(f.get("seed", 1)), f"cm/inpaint-{stem}")
                entry = c.wait(c.queue(g), timeout_s=900)
                res = tmp / f"{stem}_{n}_res.png"
                c.download(c.outputs(entry)[-1], res)
                fixed = Image.open(res).convert("RGB").resize(crop.size, Image.LANCZOS)
                paste_mask = mask.resize(crop.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(FEATHER // 3))
                img.paste(fixed, (cx0, cy0), paste_mask)
            img.save(dest)
            print("fixed", dest, flush=True)

if __name__ == "__main__":
    main()
