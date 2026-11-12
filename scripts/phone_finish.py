"""Phone-photo finish for upscaled frames: resize to a phone export size, mild sharpening,
luminance grain, JPEG. Local, no GPU.

    .venv/bin/python scripts/phone_finish.py SRC_DIR DEST_DIR [--long 2000] [--grain 5] [--quality 86] [--hdr 0.6]
"""
from __future__ import annotations

import argparse
import io
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

EXTS = (".png", ".jpg", ".jpeg", ".webp")


def phone_hdr(im: Image.Image, strength: float) -> Image.Image:
    """Phone camera look: lifted shadows, lower contrast/saturation, noise-reduction smear."""
    if strength <= 0:
        return im
    lut = [min(255, int(255 * (0.06 + 0.90 * ((i / 255) ** 0.85)))) for i in range(256)]
    hdr = im.point(lut * 3)
    hdr = ImageEnhance.Contrast(hdr).enhance(0.88)
    hdr = ImageEnhance.Color(hdr).enhance(0.93)
    w, h = hdr.size
    hdr = hdr.resize((int(w * 0.72), int(h * 0.72)), Image.BILINEAR).filter(ImageFilter.SMOOTH).resize((w, h), Image.BICUBIC)
    return Image.blend(im, hdr, min(strength, 1.0))


def finish(im: Image.Image, *, long_edge: int, grain: float, quality: int, seed: int, hdr: float = 0.0) -> Image.Image:
    im = im.convert("RGB")
    scale = long_edge / max(im.size)
    if scale < 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    im = phone_hdr(im, hdr)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.0, percent=45, threshold=2))
    if grain > 0:
        random.seed(seed)
        noise = Image.effect_noise(im.size, grain).convert("RGB")  # grey noise centred on 128
        im = ImageChops.add(im, noise, scale=1.0, offset=-128)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, subsampling=2)
    return Image.open(io.BytesIO(buf.getvalue()))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("src", type=Path)
    p.add_argument("dest", type=Path)
    p.add_argument("--long", type=int, default=2000, help="long edge in px (phone export ~2000-4000)")
    p.add_argument("--grain", type=float, default=5.0)
    p.add_argument("--quality", type=int, default=86)
    p.add_argument("--hdr", type=float, default=0.0, help="phone camera look strength 0..1")
    a = p.parse_args()
    a.dest.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(sorted(x for x in a.src.iterdir() if x.suffix.lower() in EXTS)):
        out = finish(Image.open(f), long_edge=a.long, grain=a.grain, quality=a.quality, seed=i, hdr=a.hdr)
        out.save(a.dest / f"{f.stem}.jpg", "JPEG", quality=95)
        print(f.name, "->", out.size)


if __name__ == "__main__":
    main()
