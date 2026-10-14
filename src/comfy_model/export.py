"""Prepare generated files for posting: strip metadata, label as AI, add film grain."""
from __future__ import annotations

import random
import shutil
import zlib
from pathlib import Path

from PIL import Image, ImageChops

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4"}

_EXIF_DESCRIPTION = 0x010E
_EXIF_SOFTWARE = 0x0131
AI_DESCRIPTION = "AI-generated image"
AI_SOFTWARE = "AI-generated"


def _grain_layer(size: tuple[int, int], sigma: float, seed: int) -> Image.Image:
    """Monochrome noise centered on 128 (std `sigma`), as an RGB image."""
    rng = random.Random(seed)
    gauss = rng.gauss
    data = bytes(
        min(255, max(0, int(gauss(128.0, sigma) + 0.5))) for _ in range(size[0] * size[1])
    )
    return Image.frombytes("L", size, data).convert("RGB")


def export_image(src: Path, dest_dir: Path, *, grain: float = 0.03, quality: int = 92) -> Path:
    """Export `src` into `dest_dir` and return the output path.

    Images become `<stem>.jpg` with every source metadata chunk (ComfyUI's PNG
    `prompt`/`workflow`) dropped, an AI label in EXIF and deterministic
    monochrome grain (std `grain * 255`, seeded from the file name). `.mp4`
    files are copied unchanged.
    """
    src = Path(src)
    dest_dir = Path(dest_dir)
    ext = src.suffix.lower()
    if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
        raise ValueError(f"cannot export {src.name}: unsupported file type {ext or '(none)'}")
    dest_dir.mkdir(parents=True, exist_ok=True)

    if ext in VIDEO_EXTS:
        out = dest_dir / src.name
        shutil.copyfile(src, out)
        return out

    out = dest_dir / f"{src.stem}.jpg"
    with Image.open(src) as opened:
        rgb = opened.convert("RGB")
        # convert() copies im.info (PNG text, JPEG COM comment, ICC), and the JPEG
        # writer would emit info["comment"]. Rebuild from raw pixels so nothing
        # from the source survives.
        img = Image.frombytes("RGB", rgb.size, rgb.tobytes())
    if grain > 0:
        seed = zlib.crc32(src.name.encode("utf-8"))
        noise = _grain_layer(img.size, grain * 255, seed)
        img = ImageChops.add(img, noise, scale=1.0, offset=-128)
    exif = Image.Exif()
    exif[_EXIF_DESCRIPTION] = AI_DESCRIPTION
    exif[_EXIF_SOFTWARE] = AI_SOFTWARE
    img.save(out, format="JPEG", quality=quality, exif=exif)
    return out
