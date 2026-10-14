"""ComfyUI API-format workflow templates and the pod model manifest.

A template (``workflows/<kind>.json``) is ComfyUI API format:
``{"<node_id>": {"class_type": ..., "inputs": {...}}}``. An input value that is
*exactly* the string ``"{{name}}"`` is a placeholder; ``render`` replaces it with
``values[name]`` keeping that value's type (so ``seed`` stays an ``int``).
Strings that merely contain ``{{...}}`` are left alone.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

KINDS = ("face", "dataset", "photo", "video")

PLACEHOLDERS: dict[str, set[str]] = {
    "face": {"prompt", "seed", "width", "height", "batch_size", "filename_prefix"},
    "dataset": {"prompt", "seed", "ref_image", "filename_prefix"},
    "photo": {"prompt", "seed", "width", "height", "lora_name", "lora_strength", "filename_prefix"},
    "video": {"prompt", "negative", "seed", "image", "width", "height", "length", "filename_prefix"},
}

# Input keys that name a model file inside ComfyUI/models/.
MODEL_INPUT_KEYS = frozenset({
    "ckpt_name", "unet_name", "vae_name", "clip_name", "clip_name1", "clip_name2",
    "lora_name", "model_name",
})

_PLACEHOLDER_RE = re.compile(r"^\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}$")
_HF_URL = "https://huggingface.co/{repo}/resolve/main/{path}"


class TemplateError(ValueError):
    """Bad template, bad render values, or bad model manifest."""


def _placeholder(value: Any) -> str | None:
    if isinstance(value, str):
        m = _PLACEHOLDER_RE.match(value)
        if m:
            return m.group(1)
    return None


def _walk(obj: Any):
    """Yield every leaf value (recursing through dicts and lists)."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)
    else:
        yield obj


def placeholders(template: dict) -> set[str]:
    """Names of all ``"{{name}}"`` placeholders in ``template``."""
    return {n for v in _walk(template) if (n := _placeholder(v)) is not None}


def load_template(kind: str, directory: Path = Path("workflows")) -> dict:
    if kind not in KINDS:
        raise TemplateError(f"unknown workflow kind {kind!r} (expected one of: {', '.join(KINDS)})")
    path = Path(directory) / f"{kind}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise TemplateError(f"workflow template not found: {path}") from None
    except json.JSONDecodeError as e:
        raise TemplateError(f"{path}: invalid JSON: {e}") from None
    if not isinstance(data, dict):
        raise TemplateError(f"{path}: expected an object of nodes at top level")
    return data


def render(template: dict, values: dict[str, Any]) -> dict:
    """Deep copy of ``template`` with every placeholder replaced from ``values``.

    Raises ``TemplateError`` if a placeholder has no value or a value is unused.
    """
    wanted = placeholders(template)
    missing = sorted(wanted - set(values))
    unused = sorted(set(values) - wanted)
    problems = []
    if missing:
        problems.append(f"unfilled placeholder(s): {', '.join(missing)}")
    if unused:
        problems.append(f"unused value(s): {', '.join(unused)}")
    if problems:
        raise TemplateError("; ".join(problems))

    def sub(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: sub(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sub(v) for v in obj]
        name = _placeholder(obj)
        if name is not None:
            return copy.deepcopy(values[name])
        return obj

    return sub(template)


def model_files(template: dict) -> set[str]:
    """Literal model filenames referenced by the template's loader nodes.

    Placeholders (e.g. ``"{{lora_name}}"``) and node links are skipped. Values are
    returned as written, so a detector may appear as ``"bbox/face_yolov8m.pt"``.
    """
    out: set[str] = set()
    for node in template.values():
        inputs = node.get("inputs", {}) if isinstance(node, dict) else {}
        for key, val in inputs.items():
            if key in MODEL_INPUT_KEYS and isinstance(val, str) and _placeholder(val) is None:
                out.add(val)
    return out


@dataclass(frozen=True)
class ModelSpec:
    """One entry of ``pod/models.yaml``: ``file`` downloaded into ``models/<dest>/``."""

    file: str
    dest: str
    repo: str | None = None
    path: str | None = None
    explicit_url: str | None = None

    @property
    def url(self) -> str:
        if self.explicit_url:
            return self.explicit_url
        return _HF_URL.format(repo=self.repo, path=self.path)

    @property
    def is_huggingface(self) -> bool:
        return not self.explicit_url


def load_manifest(path: Path = Path("pod/models.yaml")) -> list[ModelSpec]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise TemplateError(f"model manifest not found: {path}") from None
    items = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise TemplateError(f"{path}: expected a top-level 'models:' list")
    specs: list[ModelSpec] = []
    errors: list[str] = []
    for i, item in enumerate(items):
        label = f"{path}: entry #{i}"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be a mapping")
            continue
        file, dest = item.get("file"), item.get("dest")
        if isinstance(file, str) and file:
            label = f"{path}: {file}"
        unknown = sorted(set(item) - {"file", "dest", "repo", "path", "url"})
        if unknown:
            errors.append(f"{label}: unknown key(s) {', '.join(unknown)}")
        if not (isinstance(file, str) and file) or not (isinstance(dest, str) and dest):
            errors.append(f"{label}: 'file' and 'dest' are required strings")
            continue
        url, repo, rpath = item.get("url"), item.get("repo"), item.get("path")
        if url is not None:
            if not isinstance(url, str) or repo is not None or rpath is not None:
                errors.append(f"{label}: give either 'url' or 'repo'+'path', not both")
                continue
        elif not (isinstance(repo, str) and repo and isinstance(rpath, str) and rpath):
            errors.append(f"{label}: needs 'repo'+'path' (Hugging Face) or 'url'")
            continue
        specs.append(ModelSpec(file=file, dest=dest, repo=repo, path=rpath, explicit_url=url))
    seen: set[str] = set()
    for s in specs:
        if s.file in seen:
            errors.append(f"{path}: duplicate file {s.file}")
        seen.add(s.file)
    if errors:
        raise TemplateError("\n".join(errors))
    return specs
