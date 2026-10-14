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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

from comfy_model.config import load_secrets

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


# -- manifest URL check --------------------------------------------------------
@dataclass(frozen=True)
class UrlCheck:
    spec: ModelSpec
    status: int | None
    ok: bool
    note: str


def check_urls(specs: list[ModelSpec], hf_token: str | None = None, timeout_s: float = 20) -> list[UrlCheck]:
    """HEAD every manifest URL (no redirects followed). 2xx/3xx is fine; 401/403
    counts as reachable-but-gated; anything else (404, network error) fails.
    ``hf_token`` is sent to huggingface.co only."""
    results: list[UrlCheck] = []
    with httpx.Client(timeout=timeout_s, follow_redirects=False) as http:
        for spec in specs:
            headers = {}
            if hf_token and spec.url.startswith("https://huggingface.co/"):
                headers["Authorization"] = f"Bearer {hf_token}"
            try:
                status = http.head(spec.url, headers=headers).status_code
            except httpx.HTTPError as e:
                results.append(UrlCheck(spec, None, False, f"{type(e).__name__}: {e}"))
                continue
            if status < 400:
                results.append(UrlCheck(spec, status, True, ""))
            elif status in (401, 403):
                results.append(UrlCheck(spec, status, True, "gated: needs HF_TOKEN and accepted model license"))
            else:
                results.append(UrlCheck(spec, status, False, "not found" if status == 404 else "error"))
    return results


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args != ["--check-urls"]:
        print("usage: python -m comfy_model.workflow --check-urls", file=sys.stderr)
        return 2
    results = check_urls(load_manifest(), hf_token=load_secrets().get("HF_TOKEN") or None)
    for r in results:
        mark = "ok  " if r.ok else "FAIL"
        status = r.status if r.status is not None else "---"
        print(f"{mark} {status} {r.spec.file}  {r.spec.url}" + (f"  ({r.note})" if r.note else ""))
    failed = [r for r in results if not r.ok]
    print(f"{len(results) - len(failed)}/{len(results)} reachable")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
