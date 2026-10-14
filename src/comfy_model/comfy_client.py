"""Minimal synchronous ComfyUI HTTP API client.

Endpoints: ``POST /prompt``, ``GET /history/{id}``, ``GET /view``,
``POST /upload/image``, ``GET /system_stats``. Every failure surfaces as
``ComfyError`` with a readable message (node class + offending value for
validation errors, the URL for network errors) so a batch never hangs on a
dead pod or swallows a missing-model error.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

_OUTPUT_KEYS = ("images", "gifs", "videos")


@dataclass(frozen=True)
class OutputFile:
    filename: str
    subfolder: str
    type: str


class ComfyError(RuntimeError):
    """ComfyUI request failed.

    ``is_validation`` is True when ComfyUI rejected the prompt before running it
    (HTTP 400 from ``/prompt``, e.g. a model file missing on the volume). Such a
    failure will repeat for every item of a batch, so callers should abort; an
    execution error (OOM, etc.) is per-item.
    """

    def __init__(self, message: str, *, is_validation: bool = False):
        super().__init__(message)
        self.is_validation = is_validation


def _node_key(nid: str) -> tuple[int, int | str]:
    return (0, int(nid)) if nid.isdigit() else (1, nid)


def _format_rejection(body: Any, fallback: str) -> str:
    if not isinstance(body, dict):
        return f"ComfyUI rejected the prompt: {fallback}"
    parts: list[str] = []
    err = body.get("error")
    if isinstance(err, dict):
        head = err.get("message") or err.get("type") or "error"
        if err.get("details"):
            head += f": {err['details']}"
        parts.append(head)
    elif isinstance(err, str):
        parts.append(err)
    node_errors = body.get("node_errors")
    if isinstance(node_errors, dict):
        for nid in sorted(node_errors, key=_node_key):
            ne = node_errors[nid] if isinstance(node_errors[nid], dict) else {}
            ct = ne.get("class_type", "?")
            for e in ne.get("errors") or []:
                if not isinstance(e, dict):
                    continue
                msg = e.get("message") or e.get("type") or "error"
                if e.get("details"):
                    msg += f": {e['details']}"
                parts.append(f"node {nid} ({ct}): {msg}")
    if not parts:
        parts.append(fallback)
    return "ComfyUI rejected the prompt: " + "; ".join(parts)


def _format_execution_error(prompt_id: str, status: dict) -> str:
    detail = ""
    for m in status.get("messages") or []:
        if isinstance(m, (list, tuple)) and len(m) == 2 and m[0] == "execution_error" and isinstance(m[1], dict):
            d = m[1]
            where = f"node {d.get('node_id', '?')} ({d.get('node_type', '?')})"
            exc = d.get("exception_message") or d.get("exception_type") or "unknown error"
            detail = f": {where}: {str(exc).strip()}"
            break
    return f"ComfyUI execution failed for prompt {prompt_id}{detail}"


class ComfyClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 30,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout_s)
        self._sleep = sleep
        self._clock = clock
        self.client_id = uuid.uuid4().hex

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> ComfyClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- transport -----------------------------------------------------------
    def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            return self._http.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise ComfyError(f"cannot reach ComfyUI at {url}: {type(e).__name__}: {e}") from e

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            text = resp.text.strip()[:500]
            raise ComfyError(f"{resp.request.method} {resp.request.url} -> HTTP {resp.status_code}: {text}")

    # -- API -----------------------------------------------------------------
    def queue(self, workflow: dict) -> str:
        """Submit an API-format workflow; returns the prompt id."""
        resp = self._request("POST", "/prompt", json={"prompt": workflow, "client_id": self.client_id})
        if resp.status_code == 400:
            try:
                body = resp.json()
            except ValueError:
                body = None
            raise ComfyError(_format_rejection(body, resp.text.strip()[:500] or "HTTP 400"), is_validation=True)
        self._check(resp)
        try:
            data = resp.json()
            pid = data["prompt_id"]
        except (ValueError, KeyError, TypeError):
            raise ComfyError(f"unexpected /prompt response: {resp.text[:500]}") from None
        node_errors = data.get("node_errors")
        if node_errors:
            raise ComfyError(_format_rejection(data, "node errors"), is_validation=True)
        return str(pid)

    def wait(self, prompt_id: str, timeout_s: float = 900, poll_s: float = 2) -> dict:
        """Poll ``/history/{id}`` until the prompt finishes; returns its history entry.

        Raises ``ComfyError`` if execution failed, ``TimeoutError`` after ``timeout_s``.
        """
        deadline = self._clock() + timeout_s
        while True:
            resp = self._request("GET", f"/history/{prompt_id}")
            self._check(resp)
            try:
                data = resp.json()
            except ValueError:
                raise ComfyError(f"unexpected /history response: {resp.text[:500]}") from None
            entry = data.get(prompt_id) if isinstance(data, dict) else None
            if isinstance(entry, dict):
                status = entry.get("status") or {}
                if status.get("status_str") == "error":
                    raise ComfyError(_format_execution_error(prompt_id, status))
                if status.get("completed", True) or entry.get("outputs"):
                    return entry
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise TimeoutError(f"ComfyUI prompt {prompt_id} not finished after {timeout_s:g}s")
            self._sleep(min(poll_s, remaining))

    def outputs(self, history_entry: dict) -> list[OutputFile]:
        """All saved files (images, gifs, videos) in node-id order."""
        outs = history_entry.get("outputs") or {}
        files: list[OutputFile] = []
        for nid in sorted(outs, key=_node_key):
            node = outs[nid] or {}
            for key in _OUTPUT_KEYS:
                for item in node.get(key) or []:
                    if isinstance(item, dict) and item.get("filename"):
                        files.append(OutputFile(
                            filename=item["filename"],
                            subfolder=item.get("subfolder", "") or "",
                            type=item.get("type", "output") or "output",
                        ))
        return files

    def download(self, f: OutputFile, dest: Path) -> Path:
        """Fetch ``f`` via ``/view`` into ``dest`` atomically (temp file + rename)."""
        dest = Path(dest)
        params = {"filename": f.filename, "subfolder": f.subfolder, "type": f.type}
        resp = self._request("GET", "/view", params=params)
        self._check(resp)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.part")
        try:
            tmp.write_bytes(resp.content)
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
        return dest

    def upload_image(self, path: Path) -> str:
        """Upload into ComfyUI's input dir; returns the name to use in ``LoadImage``."""
        path = Path(path)
        with path.open("rb") as fh:
            resp = self._request(
                "POST", "/upload/image",
                files={"image": (path.name, fh, "application/octet-stream")},
                data={"overwrite": "true", "type": "input"},
            )
        self._check(resp)
        try:
            data = resp.json()
            name = data["name"]
        except (ValueError, KeyError, TypeError):
            raise ComfyError(f"unexpected /upload/image response: {resp.text[:500]}") from None
        sub = data.get("subfolder") or ""
        return f"{sub}/{name}" if sub else name

    def ping(self) -> bool:
        try:
            return self._http.get("/system_stats").status_code == 200
        except httpx.HTTPError:
            return False
