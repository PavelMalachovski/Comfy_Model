"""Texture pass over a culled dataset: low-denoise Qwen-Image redraw plus FaceDetailer.

Qwen-Image-Edit smooths skin at about 1 MP; this restores pores and flyaway hairs while
the low denoise keeps identity. Output keeps file names and captions for `cm lora prepare`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from comfy_model.batch import BUSY_MESSAGE, DEFAULT_WAIT_TIMEOUT_S, MANIFEST_NAME, BatchReport
from comfy_model.comfy_client import ComfyClient, ComfyError
from comfy_model.lora import IMAGE_EXTS, _manifest_prompts
from comfy_model.workflow import placeholders, render

GRAPH = Path("workflows/qwen/refine.json")
TEXTURE_PROMPT = (
    "37-year-old woman, dark brown eyes, defined cheekbones, naturally plump full lips, soft matte red lipstick, "
    "defined brows, elegant makeup, healthy natural skin texture with fine visible pores, flyaway hairs"
)
MAX_CONSECUTIVE_FAILURES = 3


def refine_dataset(
    src_dir: Path,
    dest_dir: Path,
    client: ComfyClient,
    *,
    on_item: Callable[[str], None] | None = None,
    graph_path: Path = GRAPH,
    room: Path | None = None,
) -> BatchReport:
    """Redraw every image left in ``src_dir`` into ``dest_dir``; finished files are skipped.

    ``graph_path`` may be any per-image graph (e.g. the SeedVR2 upscaler); values for
    placeholders it does not have (``prompt``) are dropped. ``room`` is a location plate for
    graphs with a ``room_image`` placeholder (workflows/qwen/room.json); it is uploaded once."""
    src_dir, dest_dir = Path(src_dir), Path(dest_dir)
    images = sorted(p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS) if src_dir.is_dir() else []
    if not images:
        raise ValueError(f"no images found in {src_dir}")
    captions = _manifest_prompts(src_dir)
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    wanted = placeholders(graph)
    if ("room_image" in wanted) != (room is not None):
        raise ValueError(f"{graph_path} needs --room <plate>" if room is None
                         else f"--room is only for graphs with a room_image placeholder, not {graph_path}")
    if room is not None and not Path(room).is_file():
        raise ValueError(f"room plate not found: {room}")
    room_name: str | None = None
    dest_dir.mkdir(parents=True, exist_ok=True)
    report = BatchReport()
    streak = 0
    with (dest_dir / MANIFEST_NAME).open("a", encoding="utf-8") as manifest:
        for img in images:
            dest = dest_dir / f"{img.stem}.png"
            if dest.exists():
                report.skipped.append(dest)
                continue
            if on_item:
                on_item(img.name)
            caption = captions.get(img.name, "")
            digest = hashlib.sha256(img.read_bytes()).hexdigest()
            try:
                uploaded = client.upload_image(img, name=f"{digest[:12]}-{img.name}")
                if room is not None and room_name is None:
                    room_digest = hashlib.sha256(Path(room).read_bytes()).hexdigest()[:12]
                    room_name = client.upload_image(Path(room), name=f"{room_digest}-{Path(room).name}")
                values = {
                    "prompt": f"{caption}, {TEXTURE_PROMPT}" if caption else TEXTURE_PROMPT,
                    "seed": int(digest[:8], 16),
                    "image": uploaded,
                    "filename_prefix": f"refined/{img.stem}",
                    "room_image": room_name,
                }
                workflow = render(graph, {k: v for k, v in values.items() if k in wanted})
                outs = client.outputs(client.wait(client.queue(workflow), timeout_s=DEFAULT_WAIT_TIMEOUT_S))
                if not outs:
                    raise ComfyError(f"ComfyUI returned no image for {img.name}")
                client.download(outs[0], dest)
            except TimeoutError as e:
                report.failed.append((img.name, str(e)))
                report.aborted = BUSY_MESSAGE.format(item=img.name, timeout=DEFAULT_WAIT_TIMEOUT_S)
                return report
            except ComfyError as e:
                if e.is_validation:
                    raise
                report.failed.append((img.name, str(e)))
                streak += 1
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    report.aborted = f"{streak} images in a row failed, last: {e}. Check `cm pod status`, then re-run."
                    return report
                continue
            streak = 0
            report.done.append(dest)
            manifest.write(json.dumps({"file": dest.name, "prompt": caption}, ensure_ascii=False) + "\n")
            manifest.flush()
    return report
