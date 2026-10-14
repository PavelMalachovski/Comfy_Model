import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from comfy_model import cli as cli_mod
from comfy_model import runpod_pod
from comfy_model.batch import BatchReport, run_batch
from comfy_model.cli import app
from comfy_model.comfy_client import ComfyError, OutputFile
from comfy_model.profile import Profile
from comfy_model.runpod_pod import PodInfo
from comfy_model.scenes import SceneError

PROFILE = Profile(
    name="Greta", trigger="ohwxgreta", appearance="28-year-old woman",
    style_suffix="candid photo", video_negative="blurry, deformed",
)


class FakeClient:
    """Duck-typed ComfyClient. ``errors`` maps queue call index -> exception."""

    def __init__(self, errors: dict[int, Exception] | None = None, outputs_per_prompt: int | None = None,
                 wait_errors: dict[int, Exception] | None = None):
        self.queued: list[dict] = []
        self.waits: list[float] = []
        self.wait_errors = wait_errors or {}
        self.uploads: list[tuple[Path, str | None]] = []
        self.errors = errors or {}
        self.outputs_per_prompt = outputs_per_prompt
        self._batch: dict[str, int] = {}

    def queue(self, workflow: dict) -> str:
        idx = len(self.queued)
        self.queued.append(workflow)
        if idx in self.errors:
            raise self.errors[idx]
        pid = f"p{idx}"
        batch = 1
        for node in workflow.values():
            b = node.get("inputs", {}).get("batch_size")
            if isinstance(b, int) and b > 1:
                batch = b
        self._batch[pid] = self.outputs_per_prompt if self.outputs_per_prompt is not None else batch
        return pid

    def wait(self, prompt_id: str, timeout_s: float = 900, poll_s: float = 2) -> dict:
        idx = len(self.waits)
        self.waits.append(timeout_s)
        if idx in self.wait_errors:
            raise self.wait_errors[idx]
        return {"id": prompt_id}

    def outputs(self, entry: dict) -> list[OutputFile]:
        pid = entry["id"]
        return [OutputFile(f"{pid}_{i}.dat", "", "output") for i in range(self._batch[pid])]

    def download(self, f: OutputFile, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(f.filename.encode())
        return dest

    def upload_image(self, path: Path, name: str | None = None) -> str:
        self.uploads.append((Path(path), name))
        return name or Path(path).name


def write_scenes(tmp_path: Path, body: str, name: str = "scenes.yaml") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def manifest(out: Path) -> list[dict]:
    return [json.loads(line) for line in (out / "manifest.jsonl").read_text().splitlines()]


def node_inputs(wf: dict, key: str):
    return [n["inputs"][key] for n in wf.values() if key in n.get("inputs", {})]


DESK = "scenes:\n  - id: desk\n    prompt: sitting at a desk, laptop\n    count: 2\n"


def test_rerun_skips_existing_outputs(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "desk_01.png").write_bytes(b"old")
    client = FakeClient()
    report = run_batch("photo", write_scenes(tmp_path, DESK), client, PROFILE, out, lora="greta.safetensors")
    assert len(client.queued) == 1
    assert node_inputs(client.queued[0], "filename_prefix") == ["cm/desk"] * 1
    assert [p.name for p in report.skipped] == ["desk_01.png"]
    assert [p.name for p in report.done] == ["desk_02.png"]
    assert (out / "desk_01.png").read_bytes() == b"old"
    assert [m["n"] for m in manifest(out)] == [2]


def test_full_rerun_queues_nothing(tmp_path):
    out = tmp_path / "out"
    client = FakeClient()
    scenes = write_scenes(tmp_path, DESK)
    run_batch("photo", scenes, client, PROFILE, out, lora="g.safetensors")
    again = FakeClient()
    report = run_batch("photo", scenes, again, PROFILE, out, lora="g.safetensors")
    assert again.queued == [] and report.done == [] and len(report.skipped) == 2


def test_invalid_file_queues_nothing(tmp_path):
    body = DESK + "  - id: bad\n    prompt: x\n    aspect: '3:2'\n"
    client = FakeClient()
    with pytest.raises(SceneError, match="bad"):
        run_batch("photo", write_scenes(tmp_path, body), client, PROFILE, tmp_path / "out", lora="l")
    assert client.queued == [] and client.uploads == []


def test_seed_from_scene_is_deterministic(tmp_path):
    out = tmp_path / "out"
    body = "scenes:\n  - id: s\n    prompt: standing outside\n    count: 3\n    seed: 100\n"
    client = FakeClient()
    run_batch("photo", write_scenes(tmp_path, body), client, PROFILE, out, lora="l.safetensors")
    assert [m["seed"] for m in manifest(out)] == [100, 101, 102]
    assert [node_inputs(w, "seed")[0] for w in client.queued] == [100, 101, 102]


def test_random_seed_recorded(tmp_path):
    out = tmp_path / "out"
    run_batch("photo", write_scenes(tmp_path, DESK), FakeClient(), PROFILE, out, lora="l")
    for m in manifest(out):
        assert isinstance(m["seed"], int) and 0 <= m["seed"] < 2**32


def test_photo_uses_trigger_and_lora(tmp_path):
    client = FakeClient()
    run_batch("photo", write_scenes(tmp_path, DESK), client, PROFILE, tmp_path / "o",
              lora="greta.safetensors", lora_strength=0.8)
    wf = client.queued[0]
    prompt = node_inputs(wf, "text")[0]
    assert prompt.startswith("ohwxgreta, 28-year-old woman, sitting at a desk, laptop")
    assert node_inputs(wf, "lora_name") == ["greta.safetensors"]
    assert node_inputs(wf, "strength_model") == [0.8]
    assert (896, 1120) == (node_inputs(wf, "width")[0], node_inputs(wf, "height")[0])


def test_photo_requires_lora(tmp_path):
    client = FakeClient()
    with pytest.raises(ValueError, match="--lora"):
        run_batch("photo", write_scenes(tmp_path, DESK), client, PROFILE, tmp_path / "o")
    assert client.queued == []


def test_dataset_requires_ref(tmp_path):
    client = FakeClient()
    with pytest.raises(ValueError, match="--ref"):
        run_batch("dataset", write_scenes(tmp_path, DESK), client, PROFILE, tmp_path / "o")
    with pytest.raises(ValueError, match="--ref"):
        run_batch("dataset", write_scenes(tmp_path, DESK), client, PROFILE, tmp_path / "o",
                  ref_image=tmp_path / "missing.png")
    assert client.queued == []


def test_dataset_uploads_ref_once_with_hashed_name_and_verbatim_prompt(tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"refbytes")
    expected = f"{hashlib.sha256(b'refbytes').hexdigest()[:12]}-ref.png"
    client = FakeClient()
    out = tmp_path / "o"
    run_batch("dataset", write_scenes(tmp_path, DESK), client, PROFILE, out, ref_image=ref)
    assert client.uploads == [(ref, expected)]
    assert expected in node_inputs(client.queued[0], "image")
    assert node_inputs(client.queued[0], "text") == ["sitting at a desk, laptop"]
    assert {m["kind"] for m in manifest(out)} == {"dataset"}


def test_face_one_queue_per_scene_with_batch_size(tmp_path):
    out = tmp_path / "o"
    body = "scenes:\n  - id: f1\n    prompt: neutral portrait\n    count: 3\n    seed: 7\n"
    client = FakeClient()
    report = run_batch("face", write_scenes(tmp_path, body), client, PROFILE, out)
    assert len(client.queued) == 1
    assert node_inputs(client.queued[0], "batch_size") == [3]
    assert node_inputs(client.queued[0], "text")[0].startswith("28-year-old woman, neutral portrait")
    assert "ohwxgreta" not in node_inputs(client.queued[0], "text")[0]
    assert [p.name for p in report.done] == ["f1_01.png", "f1_02.png", "f1_03.png"]
    assert [m["file"] for m in manifest(out)] == ["f1_01.png", "f1_02.png", "f1_03.png"]
    # all present -> no requeue
    again = FakeClient()
    r2 = run_batch("face", write_scenes(tmp_path, body), again, PROFILE, out)
    assert again.queued == [] and len(r2.skipped) == 3


def test_face_short_output_recorded_as_failure(tmp_path):
    body = "scenes:\n  - id: f1\n    prompt: portrait\n    count: 3\n"
    client = FakeClient(outputs_per_prompt=2)
    report = run_batch("face", write_scenes(tmp_path, body), client, PROFILE, tmp_path / "o")
    assert len(report.done) == 2
    assert len(report.failed) == 1 and report.failed[0][0] == "f1_03"


def test_video_uploads_image_relative_to_scenes_file(tmp_path):
    d = tmp_path / "scenes"
    d.mkdir()
    (d / "img.png").write_bytes(b"pic")
    body = "scenes:\n  - id: clip\n    prompt: she turns and smiles\n    image: img.png\n    aspect: '16:9'\n"
    client = FakeClient()
    out = tmp_path / "o"
    report = run_batch("video", write_scenes(d, body), client, PROFILE, out)
    wf = client.queued[0]
    assert client.uploads[0][0] == d / "img.png"
    assert client.uploads[0][1].endswith("-img.png")
    assert set(node_inputs(wf, "text")) == {"she turns and smiles", "blurry, deformed"}
    assert node_inputs(wf, "length") == [121]
    assert (node_inputs(wf, "width")[0], node_inputs(wf, "height")[0]) == (1280, 704)
    assert [p.name for p in report.done] == ["clip_01.mp4"]
    assert manifest(out)[0]["kind"] == "video"


def test_video_missing_image_raises_before_queue(tmp_path):
    body = "scenes:\n  - id: clip\n    prompt: she turns\n    image: nope.png\n"
    client = FakeClient()
    with pytest.raises(ValueError, match=r"clip.*nope\.png"):
        run_batch("video", write_scenes(tmp_path, body), client, PROFILE, tmp_path / "o")
    assert client.queued == [] and client.uploads == []


def test_execution_error_recorded_and_batch_continues(tmp_path):
    out = tmp_path / "o"
    client = FakeClient(errors={0: ComfyError("OOM at node 7")})
    report = run_batch("photo", write_scenes(tmp_path, DESK), client, PROFILE, out, lora="l")
    assert report.failed == [("desk_01", "OOM at node 7")]
    assert [p.name for p in report.done] == ["desk_02.png"]


def test_missing_model_aborts_batch(tmp_path):
    out = tmp_path / "o"
    client = FakeClient(errors={0: ComfyError("node 2 (LoraLoaderModelOnly): lora_name not in list", is_validation=True)})
    with pytest.raises(ComfyError, match="lora_name"):
        run_batch("photo", write_scenes(tmp_path, DESK), client, PROFILE, out, lora="l")
    assert len(client.queued) == 1


def test_manifest_lines_written(tmp_path):
    out = tmp_path / "o"
    client = FakeClient()
    run_batch("photo", write_scenes(tmp_path, DESK), client, PROFILE, out, lora="l")
    lines = manifest(out)
    assert len(lines) == 2
    for n, m in enumerate(lines, start=1):
        assert set(m) == {"scene_id", "n", "seed", "prompt", "file", "kind", "tier"}
        assert m["scene_id"] == "desk" and m["n"] == n and m["kind"] == "photo"
        assert m["tier"] == "instagram"
        assert m["file"] == f"desk_{n:02d}.png"
        assert m["prompt"].startswith("ohwxgreta, ")
        assert (out / m["file"]).exists()
    # append mode across runs
    run_batch("photo", write_scenes(tmp_path, DESK.replace("count: 2", "count: 3")), FakeClient(),
              PROFILE, out, lora="l")
    assert len(manifest(out)) == 3


def test_manifest_records_scene_tier(tmp_path):
    out = tmp_path / "o"
    body = "defaults:\n  tier: fanvue\nscenes:\n  - id: a\n    prompt: lace set\n    count: 1\n"
    run_batch("photo", write_scenes(tmp_path, body), FakeClient(), PROFILE, out, lora="l")
    assert [m["tier"] for m in manifest(out)] == ["fanvue"]


@pytest.mark.parametrize("kind,expected", [("photo", 900), ("face", 900), ("video", 2700)])
def test_wait_timeout_per_kind(tmp_path, kind, expected):
    d = tmp_path / "s"
    d.mkdir()
    (d / "img.png").write_bytes(b"pic")
    body = DESK if kind != "video" else "scenes:\n  - id: clip\n    prompt: she turns\n    image: img.png\n"
    client = FakeClient()
    run_batch(kind, write_scenes(d, body), client, PROFILE, tmp_path / "o", lora="l")
    assert client.waits and set(client.waits) == {expected}


TWO_SCENES = DESK + "  - id: cafe\n    prompt: in a cafe\n    count: 2\n"


def test_timeout_stops_batch_without_queueing_more(tmp_path):
    out = tmp_path / "o"
    client = FakeClient(wait_errors={1: TimeoutError("ComfyUI prompt p1 not finished after 900s")})
    seen = []
    report = run_batch("photo", write_scenes(tmp_path, TWO_SCENES), client, PROFILE, out, lora="l",
                       on_scene=lambda *a: seen.append(a))
    assert len(client.queued) == 2  # nothing queued after the timed-out prompt
    assert [p.name for p in report.done] == ["desk_01.png"]
    assert report.failed == [("desk_02", "ComfyUI prompt p1 not finished after 900s")]
    assert report.aborted and "still busy" in report.aborted and "re-run" in report.aborted
    assert seen == [("desk", 1, 0, 1)]


def test_timeout_stops_face_batch(tmp_path):
    body = ("scenes:\n  - id: f1\n    prompt: portrait\n    count: 2\n"
            "  - id: f2\n    prompt: portrait outdoors\n    count: 2\n")
    client = FakeClient(wait_errors={0: TimeoutError("not finished")})
    report = run_batch("face", write_scenes(tmp_path, body), client, PROFILE, tmp_path / "o")
    assert len(client.queued) == 1
    assert report.aborted and report.failed[0][0] == "f1_01"


def test_report_is_dataclass_of_lists():
    r = BatchReport()
    assert r.done == [] and r.skipped == [] and r.failed == [] and r.aborted is None


# -- CLI ---------------------------------------------------------------------
def test_cli_batch_with_fake_client(tmp_path, monkeypatch):
    fake = FakeClient()
    seen = {}

    def factory(url):
        seen["url"] = url
        return fake

    monkeypatch.setattr(cli_mod, "_make_client", factory)
    scenes = write_scenes(tmp_path, DESK)
    out = tmp_path / "out"
    res = CliRunner().invoke(app, ["batch", "photo", str(scenes), "--out", str(out),
                                   "--lora", "greta.safetensors", "--url", "http://pod:8188"])
    assert res.exit_code == 0, res.output
    assert seen["url"] == "http://pod:8188"
    assert "desk" in res.output and "2 done" in res.output
    assert (out / "desk_02.png").exists()


def test_cli_batch_scene_error_exits_1(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_mod, "_make_client", lambda url: FakeClient())
    scenes = write_scenes(tmp_path, "scenes:\n  - id: Bad_ID\n    prompt: x\n")
    res = CliRunner().invoke(app, ["batch", "face", str(scenes), "--url", "http://x"])
    assert res.exit_code == 1
    assert "Bad_ID" in res.output


def test_cli_batch_url_from_pod_json(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli_mod, "_make_client", lambda url: seen.setdefault("url", url) and FakeClient())
    scenes = write_scenes(tmp_path, DESK)
    monkeypatch.chdir(tmp_path)
    # current_pod() checks the pod still exists via the RunPod API
    monkeypatch.setattr(runpod_pod, "exists", lambda pod_id: pod_id == "abc")
    runpod_pod.save_state(PodInfo("abc", "203.0.113.7", 40122, "https://abc-8188.proxy.runpod.net"),
                          tmp_path / ".cm" / "pod.json")
    # profile + workflows are read relative to cwd, so run from the repo content
    repo = Path(__file__).resolve().parent.parent
    for sub in ("character", "workflows"):
        (tmp_path / sub).symlink_to(repo / sub)
    res = CliRunner().invoke(app, ["batch", "face", str(scenes), "--out", str(tmp_path / "o")])
    assert res.exit_code == 0, res.output
    assert seen["url"] == "https://abc-8188.proxy.runpod.net"


def test_cli_batch_no_pod_exits_1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scenes = write_scenes(tmp_path, DESK)
    res = CliRunner().invoke(app, ["batch", "face", str(scenes)])
    assert res.exit_code == 1
    assert "no running pod" in res.output and "cm pod up" in res.output


def _repo_cwd(tmp_path, monkeypatch):
    """cwd = tmp_path with the repo's character/ and workflows/ (read relative to cwd)."""
    monkeypatch.chdir(tmp_path)
    repo = Path(__file__).resolve().parent.parent
    for sub in ("character", "workflows"):
        (tmp_path / sub).symlink_to(repo / sub)


class _FixedDate:
    @staticmethod
    def today():
        import datetime
        return datetime.date(2026, 10, 20)


def test_cli_batch_default_out_is_date_and_scene_file(tmp_path, monkeypatch):
    _repo_cwd(tmp_path, monkeypatch)
    monkeypatch.setattr(cli_mod, "date", _FixedDate)
    monkeypatch.setattr(cli_mod, "_make_client", lambda url: FakeClient())
    scenes = write_scenes(tmp_path, DESK, name="instagram.yaml")
    res = CliRunner().invoke(app, ["batch", "photo", str(scenes), "--lora", "l.safetensors",
                                   "--url", "http://pod:8188"])
    assert res.exit_code == 0, res.output
    out = Path("out") / "2026-10-20-instagram"
    assert (tmp_path / out / "desk_01.png").exists()
    first = res.output.splitlines()[0]
    assert str(out) in first and "--out" in first  # printed before any work: resumable after midnight


def test_cli_batch_timeout_exits_1_with_resume_hint(tmp_path, monkeypatch):
    client = FakeClient(wait_errors={0: TimeoutError("not finished after 900s")})
    monkeypatch.setattr(cli_mod, "_make_client", lambda url: client)
    out = tmp_path / "o"
    res = CliRunner().invoke(app, ["batch", "photo", str(write_scenes(tmp_path, TWO_SCENES)),
                                   "--out", str(out), "--lora", "l", "--url", "http://x"])
    assert res.exit_code == 1
    assert len(client.queued) == 1
    assert "still busy" in res.output and "re-run" in res.output
