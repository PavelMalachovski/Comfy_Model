"""Plain SDXL text-to-image for faceless Fanvue body frames (no persona LoRA: SDXL cannot load the Qwen LoRA).
The body description comes from character/profile_body_40.yaml, so frames match Roxana's build, not her face.
Built-in ComfyUI nodes only.

Spec (YAML): checkpoint, optional negative, defaults {count, width, height}, scenes [{id, seed, prompt}].
  python scripts/sdxl_gen.py scenes/fanvue_sdxl_body.yaml --out out/dev/fanvue-sdxl-body --url http://127.0.0.1:8192
"""
import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, "src")
from comfy_model.comfy_client import ComfyClient  # noqa: E402
from comfy_model.profile import load_profile  # noqa: E402
from comfy_model.safety import check_prompt  # noqa: E402

NEG = ("face, head, eyes, lips, portrait, child, teen, underage, young looking, deformed anatomy, extra limbs, "
       "extra fingers, fused fingers, bad hands, blurry, low quality, plastic skin, airbrushed, cartoon, 3d render, "
       "text, watermark, sex toy, man, two people")
STYLE = "raw photo, shot on iPhone, natural window light, real skin texture with visible pores, high detail"


def graph(ckpt, prompt, negative, w, h, seed, prefix):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": negative}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
              "latent_image": ["4", 0], "seed": seed, "steps": 35, "cfg": 5.0, "sampler_name": "dpmpp_2m",
              "scheduler": "karras", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--only", help="comma-separated scene ids")
    ap.add_argument("--profile", default="character/profile_body_40.yaml")
    a = ap.parse_args()
    spec = yaml.safe_load(Path(a.spec).read_text())
    body = load_profile(Path(a.profile)).appearance
    d = spec.get("defaults", {})
    count, w, h = int(d.get("count", 2)), int(d.get("width", 896)), int(d.get("height", 1152))
    negative = spec.get("negative", NEG)
    prompts = {s["id"]: f"{s['prompt']}, {body}, {STYLE}" for s in spec["scenes"]}
    for sid, p in prompts.items():
        bad = check_prompt(p, "fanvue")
        assert not bad, (sid, bad)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with ComfyClient(a.url) as c:
        for s in spec["scenes"]:
            if a.only and s["id"] not in a.only.split(","):
                continue
            for n in range(1, count + 1):
                dest = out / f"{s['id']}_{n:02d}.png"
                if dest.exists():
                    print("skip", dest.name); continue
                g = graph(spec["checkpoint"], prompts[s["id"]], negative, w, h, int(s["seed"]) + n - 1,
                          f"cm/sdxl-{s['id']}")
                entry = c.wait(c.queue(g), timeout_s=900)
                c.download(c.outputs(entry)[-1], dest)
                print("saved", dest, flush=True)


if __name__ == "__main__":
    main()
