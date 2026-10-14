import json
from pathlib import Path

import httpx
import pytest
import respx

from comfy_model.comfy_client import ComfyClient, ComfyError, OutputFile

BASE = "http://comfy.test:8188"


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def client(clock):
    c = ComfyClient(BASE, sleep=clock.sleep, clock=clock)
    yield c
    c.close()


@respx.mock
def test_queue_returns_prompt_id(client):
    route = respx.post(f"{BASE}/prompt").mock(
        return_value=httpx.Response(200, json={"prompt_id": "abc-123", "number": 1, "node_errors": {}}))
    wf = {"1": {"class_type": "X", "inputs": {}}}
    assert client.queue(wf) == "abc-123"
    sent = json.loads(route.calls.last.request.content)
    assert sent["prompt"] == wf
    assert sent["client_id"]


@respx.mock
def test_queue_node_error_is_readable(client):
    body = {
        "error": {"type": "prompt_outputs_failed_validation", "message": "Prompt outputs failed validation",
                  "details": "", "extra_info": {}},
        "node_errors": {
            "37": {
                "errors": [{
                    "type": "value_not_in_list", "message": "Value not in list",
                    "details": "unet_name: 'wan2.2_ti2v_5B_fp16.safetensors' not in []",
                    "extra_info": {"input_name": "unet_name"},
                }],
                "dependent_outputs": ["58"],
                "class_type": "UNETLoader",
            }
        },
    }
    respx.post(f"{BASE}/prompt").mock(return_value=httpx.Response(400, json=body))
    with pytest.raises(ComfyError) as ei:
        client.queue({"37": {"class_type": "UNETLoader", "inputs": {}}})
    msg = str(ei.value)
    assert "UNETLoader" in msg
    assert "wan2.2_ti2v_5B_fp16.safetensors" in msg
    assert "37" in msg
    assert ei.value.is_validation is True


@respx.mock
def test_queue_400_without_json_is_readable(client):
    respx.post(f"{BASE}/prompt").mock(return_value=httpx.Response(400, text="bad things"))
    with pytest.raises(ComfyError, match="bad things") as ei:
        client.queue({})
    assert ei.value.is_validation is True


@respx.mock
def test_queue_server_error(client):
    respx.post(f"{BASE}/prompt").mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(ComfyError, match="500") as ei:
        client.queue({})
    assert ei.value.is_validation is False


@respx.mock
def test_network_error_names_url(client):
    respx.post(f"{BASE}/prompt").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(ComfyError, match="comfy.test:8188/prompt") as ei:
        client.queue({})
    assert ei.value.is_validation is False


def _history(pid: str, status: str = "success", messages=None, outputs=None) -> dict:
    return {pid: {
        "prompt": [],
        "outputs": outputs or {},
        "status": {"status_str": status, "completed": status == "success", "messages": messages or []},
    }}


@respx.mock
def test_wait_polls_until_history_present(client, clock):
    route = respx.get(f"{BASE}/history/p1").mock(side_effect=[
        httpx.Response(200, json={}),
        httpx.Response(200, json={}),
        httpx.Response(200, json=_history("p1", outputs={"9": {"images": []}})),
    ])
    entry = client.wait("p1", timeout_s=60, poll_s=2)
    assert entry["outputs"] == {"9": {"images": []}}
    assert route.call_count == 3
    assert clock.sleeps == [2, 2]


@respx.mock
def test_wait_raises_on_execution_error(client):
    msgs = [
        ["execution_start", {"prompt_id": "p1"}],
        ["execution_error", {"prompt_id": "p1", "node_id": "12", "node_type": "KSampler",
                             "exception_type": "torch.OutOfMemoryError",
                             "exception_message": "CUDA out of memory"}],
    ]
    respx.get(f"{BASE}/history/p1").mock(
        return_value=httpx.Response(200, json=_history("p1", "error", msgs)))
    with pytest.raises(ComfyError) as ei:
        client.wait("p1")
    msg = str(ei.value)
    assert "CUDA out of memory" in msg and "KSampler" in msg and "p1" in msg
    assert ei.value.is_validation is False


@respx.mock
def test_wait_raises_on_execution_error_without_messages(client):
    respx.get(f"{BASE}/history/p1").mock(return_value=httpx.Response(200, json=_history("p1", "error")))
    with pytest.raises(ComfyError, match="p1"):
        client.wait("p1")


@respx.mock
def test_wait_timeout(client, clock):
    route = respx.get(f"{BASE}/history/p1").mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(TimeoutError, match="p1"):
        client.wait("p1", timeout_s=10, poll_s=2)
    assert route.call_count >= 5
    assert clock.t <= 12


def test_outputs_collects_images_and_videos(client):
    entry = {"outputs": {
        "9": {"images": [{"filename": "a_00001_.png", "subfolder": "face", "type": "output"},
                         {"filename": "a_00002_.png", "subfolder": "face", "type": "output"}]},
        "12": {"gifs": [{"filename": "v_00001.webp", "subfolder": "", "type": "output"}]},
        "15": {"videos": [{"filename": "v_00001_.mp4", "subfolder": "vid", "type": "output"}]},
        "16": {"text": ["ignored"]},
    }}
    files = client.outputs(entry)
    assert set(files) == {
        OutputFile("a_00001_.png", "face", "output"),
        OutputFile("a_00002_.png", "face", "output"),
        OutputFile("v_00001.webp", "", "output"),
        OutputFile("v_00001_.mp4", "vid", "output"),
    }
    # stable order: by node id, then position
    assert [f.filename for f in files] == ["a_00001_.png", "a_00002_.png", "v_00001.webp", "v_00001_.mp4"]


def test_outputs_empty(client):
    assert client.outputs({}) == []


@respx.mock
def test_download_writes_file(client, tmp_path: Path):
    route = respx.get(f"{BASE}/view").mock(return_value=httpx.Response(200, content=b"\x89PNGdata"))
    dest = tmp_path / "out" / "x.png"
    got = client.download(OutputFile("a_00001_.png", "face", "output"), dest)
    assert got == dest
    assert dest.read_bytes() == b"\x89PNGdata"
    params = dict(route.calls.last.request.url.params)
    assert params == {"filename": "a_00001_.png", "subfolder": "face", "type": "output"}
    assert list(dest.parent.iterdir()) == [dest]  # no leftover temp file


@respx.mock
def test_download_error_leaves_no_file(client, tmp_path: Path):
    respx.get(f"{BASE}/view").mock(return_value=httpx.Response(404, text="nope"))
    dest = tmp_path / "x.png"
    with pytest.raises(ComfyError, match="404"):
        client.download(OutputFile("a.png", "", "output"), dest)
    assert not dest.exists()
    assert list(tmp_path.iterdir()) == []


@respx.mock
def test_upload_image_returns_name(client, tmp_path: Path):
    img = tmp_path / "ref.png"
    img.write_bytes(b"\x89PNGref")
    route = respx.post(f"{BASE}/upload/image").mock(
        return_value=httpx.Response(200, json={"name": "ref.png", "subfolder": "", "type": "input"}))
    assert client.upload_image(img) == "ref.png"
    req = route.calls.last.request
    assert b"ref.png" in req.content and b"\x89PNGref" in req.content


@respx.mock
def test_upload_image_with_subfolder(client, tmp_path: Path):
    img = tmp_path / "ref.png"
    img.write_bytes(b"x")
    respx.post(f"{BASE}/upload/image").mock(
        return_value=httpx.Response(200, json={"name": "ref.png", "subfolder": "cm", "type": "input"}))
    assert client.upload_image(img) == "cm/ref.png"


@respx.mock
def test_ping(client):
    respx.get(f"{BASE}/system_stats").mock(return_value=httpx.Response(200, json={"system": {}}))
    assert client.ping() is True


@respx.mock
def test_ping_false_on_error(client):
    respx.get(f"{BASE}/system_stats").mock(side_effect=httpx.ConnectError("refused"))
    assert client.ping() is False


@respx.mock
def test_ping_false_on_bad_status(client):
    respx.get(f"{BASE}/system_stats").mock(return_value=httpx.Response(502))
    assert client.ping() is False


def test_base_url_trailing_slash(clock):
    with respx.mock:
        respx.get(f"{BASE}/system_stats").mock(return_value=httpx.Response(200, json={}))
        with ComfyClient(BASE + "/", sleep=clock.sleep, clock=clock) as c:
            assert c.ping() is True
