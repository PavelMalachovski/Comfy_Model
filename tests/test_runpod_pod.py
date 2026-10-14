import json
import logging
import os
import signal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from comfy_model import cli as cli_mod
from comfy_model import remote, runpod_pod
from comfy_model.cli import app
from comfy_model.config import ConfigError, Secrets, Settings
from comfy_model.runpod_pod import PodError, PodInfo

SETTINGS = Settings(
    gpu_type="NVIDIA GeForce RTX 4090", datacenter="EU-RO-1",
    image="runpod/pytorch:test", volume_gb=100, idle_timeout_min=15,
    max_runtime_h=4, comfy_port=8188, remote_root="/workspace",
)
SECRET_VALUES = {
    "RUNPOD_API_KEY": "rpa_SECRETKEY_0123456789",
    "RUNPOD_VOLUME_ID": "vol-secret-xyz",
    "HF_TOKEN": "hf_SECRETTOKEN_abcdef",
}
PUBKEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakeKeyForTests op@laptop"

READY = {
    "id": "pod1",
    "desiredStatus": "RUNNING",
    "runtime": {"ports": [
        {"ip": "100.64.0.2", "isIpPublic": False, "privatePort": 22, "publicPort": 22, "type": "tcp"},
        {"ip": "10.0.0.1", "isIpPublic": False, "privatePort": 8188, "publicPort": 8188, "type": "http"},
        {"ip": "203.0.113.7", "isIpPublic": True, "privatePort": 22, "publicPort": 40122, "type": "tcp"},
    ]},
}
STARTING = {"id": "pod1", "desiredStatus": "RUNNING", "runtime": None}


class FakeRunpod:
    """Stands in for the ``runpod`` SDK module. ``pods`` maps id -> list of
    successive ``get_pod`` answers (last one repeats); missing id -> None."""

    def __init__(self, pods=None, create_id="pod1"):
        self.api_key = None
        self.pods = pods or {}
        self.create_id = create_id
        self.created: list[dict] = []
        self.terminated: list[str] = []
        self.get_calls = 0

    def create_pod(self, **kw):
        self.created.append(kw)
        return {"id": self.create_id, "desiredStatus": "RUNNING"}

    def get_pod(self, pod_id):
        self.get_calls += 1
        seq = self.pods.get(pod_id)
        if not seq:
            return None
        return seq.pop(0) if len(seq) > 1 else seq[0]

    def terminate_pod(self, pod_id):
        self.terminated.append(pod_id)
        self.pods.pop(pod_id, None)


@pytest.fixture
def fake(monkeypatch):
    f = FakeRunpod()
    f.api_key = "preset"
    monkeypatch.setattr(runpod_pod, "runpod", f)
    return f


@pytest.fixture
def pubkey(tmp_path):
    p = tmp_path / "id_ed25519.pub"
    p.write_text(PUBKEY + "\n")
    return p


def assert_no_secrets(text: str):
    for name, value in SECRET_VALUES.items():
        assert value not in text, f"{name} leaked"


# -- runpod_pod ---------------------------------------------------------------
def test_create_passes_volume_and_env(fake, pubkey, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    pod_id = runpod_pod.create(SETTINGS, Secrets(SECRET_VALUES), pubkey_path=pubkey)
    assert pod_id == "pod1"
    assert fake.api_key == SECRET_VALUES["RUNPOD_API_KEY"]
    (kw,) = fake.created
    assert kw["network_volume_id"] == "vol-secret-xyz"
    assert kw["cloud_type"] == "SECURE"
    assert kw["gpu_type_id"] == "NVIDIA GeForce RTX 4090"
    assert kw["image_name"] == "runpod/pytorch:test"
    assert kw["data_center_id"] == "EU-RO-1"
    assert kw["volume_mount_path"] == "/workspace"
    assert kw["ports"] == "8188/http,22/tcp"
    assert kw["support_public_ip"] is True
    assert kw["gpu_count"] == 1
    assert kw["container_disk_in_gb"] == 20
    env = kw["env"]
    assert env["PUBLIC_KEY"] == PUBKEY
    assert env["RUNPOD_API_KEY"] == SECRET_VALUES["RUNPOD_API_KEY"]
    assert env["HF_TOKEN"] == SECRET_VALUES["HF_TOKEN"]
    assert env["IDLE_TIMEOUT_MIN"] == "15"
    assert env["MAX_RUNTIME_H"] == "4"
    assert all(isinstance(v, str) for v in env.values())
    out = capsys.readouterr()
    assert_no_secrets(out.out + out.err + caplog.text)


def test_create_without_hf_token_omits_it(fake, pubkey):
    secrets = Secrets({k: v for k, v in SECRET_VALUES.items() if k != "HF_TOKEN"})
    runpod_pod.create(SETTINGS, secrets, pubkey_path=pubkey)
    assert "HF_TOKEN" not in fake.created[0]["env"]


def test_missing_api_key_message(fake, pubkey):
    with pytest.raises(ConfigError, match=r"RUNPOD_API_KEY.*\.env"):
        runpod_pod.create(SETTINGS, Secrets({"RUNPOD_VOLUME_ID": "v"}), pubkey_path=pubkey)
    assert fake.created == []


def test_missing_volume_id_message(fake, pubkey):
    with pytest.raises(ConfigError, match=r"RUNPOD_VOLUME_ID.*\.env"):
        runpod_pod.create(SETTINGS, Secrets({"RUNPOD_API_KEY": "k"}), pubkey_path=pubkey)
    assert fake.created == []


def test_missing_pubkey_message(fake, tmp_path):
    with pytest.raises(ConfigError, match="ssh-keygen"):
        runpod_pod.create(SETTINGS, Secrets(SECRET_VALUES), pubkey_path=tmp_path / "nope.pub")
    assert fake.created == []


def test_wait_ready_parses_ssh_port(fake):
    fake.pods["pod1"] = [STARTING, STARTING, READY]
    sleeps = []
    info = runpod_pod.wait_ready("pod1", timeout_s=600, sleep=sleeps.append, clock=lambda: 0.0)
    assert info == PodInfo(id="pod1", ssh_host="203.0.113.7", ssh_port=40122,
                           comfy_url="https://pod1-8188.proxy.runpod.net")
    assert len(sleeps) == 2


def test_wait_ready_times_out(fake):
    fake.pods["pod1"] = [STARTING]
    t = [0.0]

    def sleep(s):
        t[0] += s

    with pytest.raises(PodError, match="not ready"):
        runpod_pod.wait_ready("pod1", timeout_s=30, poll_s=5, sleep=sleep, clock=lambda: t[0])
    assert t[0] == pytest.approx(30)


def test_wait_ready_pod_vanished(fake):
    with pytest.raises(PodError, match="disappeared"):
        runpod_pod.wait_ready("pod1", sleep=lambda s: None, clock=lambda: 0.0)


def test_exists_and_terminate(fake):
    fake.pods["pod1"] = [READY]
    assert runpod_pod.exists("pod1") is True
    assert runpod_pod.exists("other") is False
    runpod_pod.terminate("pod1")
    assert fake.terminated == ["pod1"]
    assert runpod_pod.exists("pod1") is False


def test_exists_false_for_terminated_status(fake):
    fake.pods["pod1"] = [{**READY, "desiredStatus": "TERMINATED"}]
    assert runpod_pod.exists("pod1") is False


def test_api_key_loaded_lazily(monkeypatch, tmp_path):
    f = FakeRunpod(pods={"pod1": [READY]})
    monkeypatch.setattr(runpod_pod, "runpod", f)
    monkeypatch.setattr(runpod_pod, "load_secrets", lambda: Secrets({"RUNPOD_API_KEY": "lazy"}))
    assert runpod_pod.exists("pod1")
    assert f.api_key == "lazy"


def test_state_roundtrip(fake, tmp_path):
    state = tmp_path / ".cm" / "pod.json"
    info = PodInfo("pod1", "203.0.113.7", 40122, "https://pod1-8188.proxy.runpod.net")
    runpod_pod.save_state(info, state)
    data = json.loads(state.read_text())
    assert data["id"] == "pod1" and data["ssh_port"] == 40122 and data["created_at"]
    fake.pods["pod1"] = [READY]
    assert runpod_pod.current_pod(state) == info
    assert state.exists()


def test_status_clears_stale_state(fake, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = Path(".cm/pod.json")
    info = PodInfo("gone", "203.0.113.7", 40122, "https://gone-8188.proxy.runpod.net")
    runpod_pod.save_state(info, state)
    # get_pod returns None: the watchdog already removed the pod
    assert runpod_pod.current_pod(state) is None
    assert not state.exists()

    runpod_pod.save_state(info, state)
    res = CliRunner().invoke(app, ["pod", "status"])
    assert res.exit_code == 0, res.output
    assert "no running pod" in res.output
    assert not state.exists()


def test_current_pod_no_state(fake, tmp_path):
    assert runpod_pod.current_pod(tmp_path / "pod.json") is None
    assert fake.get_calls == 0


def test_current_pod_corrupt_state_raises(fake, tmp_path):
    state = tmp_path / "pod.json"
    state.write_text("{not json")
    with pytest.raises(PodError, match="pod.json"):
        runpod_pod.current_pod(state)
    assert state.exists()  # never silently forget a possibly billed pod


def test_current_pod_api_error_keeps_state(monkeypatch, tmp_path):
    class Boom(FakeRunpod):
        def get_pod(self, pod_id):
            raise RuntimeError("network down")

    f = Boom()
    f.api_key = "k"
    monkeypatch.setattr(runpod_pod, "runpod", f)
    state = tmp_path / "pod.json"
    runpod_pod.save_state(PodInfo("pod1", "h", 1, "u"), state)
    with pytest.raises(RuntimeError):
        runpod_pod.current_pod(state)
    assert state.exists()


# -- CLI ------------------------------------------------------------------------
class FakeRemote:
    """Records argv passed to remote.run; ``fail`` maps a substring of the
    joined argv to the exit code to return."""

    def __init__(self, fail=None):
        self.calls: list[list[str]] = []
        self.fail = fail or {}

    def __call__(self, argv):
        self.calls.append(list(argv))
        joined = " ".join(argv)
        for needle, rc in self.fail.items():
            if needle in joined:
                return rc
        return 0


class PingClient:
    def __init__(self, results):
        self.results = results

    def ping(self):
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]

    def close(self):
        pass


@pytest.fixture
def cli_env(tmp_path, monkeypatch, pubkey):
    """CLI run from an isolated cwd with fake settings/secrets/RunPod/SSH."""
    monkeypatch.chdir(tmp_path)
    for p in ("pod", "workflows"):
        (tmp_path / p).mkdir()
    (tmp_path / "src" / "comfy_model").mkdir(parents=True)
    (tmp_path / "src" / "comfy_model" / "watchdog.py").write_text("# wd\n")
    f = FakeRunpod(pods={"pod1": [READY]})
    monkeypatch.setattr(runpod_pod, "runpod", f)
    monkeypatch.setattr(runpod_pod, "PUBKEY_PATH", pubkey)
    monkeypatch.setattr(cli_mod, "load_settings", lambda: SETTINGS)
    monkeypatch.setattr(cli_mod, "load_secrets", lambda: Secrets(SECRET_VALUES))
    rem = FakeRemote()
    monkeypatch.setattr(remote, "run", rem)
    monkeypatch.setattr(cli_mod, "_sleep", lambda s: None)
    t = [0.0]

    def clock():
        t[0] += 1.0
        return t[0]

    monkeypatch.setattr(cli_mod, "_clock", clock)
    monkeypatch.setattr(cli_mod, "_make_client", lambda url: PingClient([False, True]))
    return {"runpod": f, "remote": rem, "state": tmp_path / ".cm" / "pod.json", "tmp": tmp_path}


def test_up_happy_path(cli_env, caplog):
    caplog.set_level(logging.DEBUG)
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 0, res.output
    f, rem = cli_env["runpod"], cli_env["remote"]
    assert len(f.created) == 1 and f.terminated == []
    joined = [" ".join(c) for c in rem.calls]
    rsync = [c for c in rem.calls if c[0] == "rsync"]
    assert len(rsync) == 1
    assert rsync[0][-4:] == ["pod", "workflows", "src/comfy_model/watchdog.py", "root@203.0.113.7:/workspace/cm/"]
    boot = [i for i, j in enumerate(joined) if j.endswith("bash /workspace/cm/pod/bootstrap.sh")]
    wd = [i for i, j in enumerate(joined) if "watchdog.pid" in j]
    assert boot and wd and boot[0] < wd[0]
    assert joined.index(" ".join(rsync[0])) < boot[0]
    data = json.loads(cli_env["state"].read_text())
    assert data["id"] == "pod1" and data["comfy_url"] == "https://pod1-8188.proxy.runpod.net"
    assert "https://pod1-8188.proxy.runpod.net" in res.output
    assert "auto-off after 15 min idle / 4 h max" in res.output
    assert_no_secrets(res.output + caplog.text)


def test_up_refuses_when_running(cli_env):
    runpod_pod.save_state(PodInfo("pod1", "203.0.113.7", 40122, "https://pod1-8188.proxy.runpod.net"),
                          cli_env["state"])
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert "already running" in res.output and "pod1" in res.output
    assert cli_env["runpod"].created == []
    assert cli_env["remote"].calls == []


def test_up_missing_api_key(cli_env, monkeypatch):
    monkeypatch.setattr(cli_mod, "load_secrets", lambda: Secrets({"RUNPOD_VOLUME_ID": "v"}))
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert "RUNPOD_API_KEY" in res.output and ".env" in res.output
    assert cli_env["runpod"].created == []


@pytest.mark.parametrize("needle", ["rsync", "bootstrap.sh", "watchdog.pid"])
def test_up_failure_terminates_pod(cli_env, monkeypatch, needle):
    cli_env["remote"].fail = {needle: 1}
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert cli_env["runpod"].terminated == ["pod1"]
    assert not cli_env["state"].exists()
    assert "terminat" in res.output
    assert_no_secrets(res.output)


def test_up_watchdog_dead_message(cli_env):
    cli_env["remote"].fail = {"watchdog.pid": 1}
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert "watchdog" in res.output


def test_up_comfy_ping_timeout_terminates(cli_env, monkeypatch):
    monkeypatch.setattr(cli_mod, "_make_client", lambda url: PingClient([False]))
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert "ComfyUI" in res.output
    assert cli_env["runpod"].terminated == ["pod1"]
    assert not cli_env["state"].exists()


def test_up_wait_timeout_terminates(cli_env, monkeypatch):
    cli_env["runpod"].pods["pod1"] = [STARTING]
    monkeypatch.setattr(runpod_pod, "time", type("T", (), {
        "sleep": staticmethod(lambda s: None),
        "monotonic": staticmethod(iter(range(0, 10**6, 100)).__next__),
    }))
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert cli_env["runpod"].terminated == ["pod1"]
    assert not cli_env["state"].exists()


def test_up_missing_local_files_creates_nothing(cli_env):
    (cli_env["tmp"] / "src" / "comfy_model" / "watchdog.py").unlink()
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert "watchdog.py" in res.output
    assert cli_env["runpod"].created == []


def test_up_error_message_is_redacted(cli_env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError(f"bad request with key {SECRET_VALUES['RUNPOD_API_KEY']}")

    monkeypatch.setattr(cli_env["runpod"], "create_pod", boom)
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert "bad request" in res.output
    assert_no_secrets(res.output)


def test_status_running(cli_env):
    runpod_pod.save_state(PodInfo("pod1", "203.0.113.7", 40122, "https://pod1-8188.proxy.runpod.net"),
                          cli_env["state"])
    res = CliRunner().invoke(app, ["pod", "status"])
    assert res.exit_code == 0, res.output
    assert "pod1" in res.output and "https://pod1-8188.proxy.runpod.net" in res.output
    assert "ssh" in res.output and "40122" in res.output


def test_down_no_state(cli_env):
    res = CliRunner().invoke(app, ["pod", "down"])
    assert res.exit_code == 0
    assert "no running pod" in res.output
    assert cli_env["runpod"].terminated == []


def test_down_terminates_and_clears(cli_env):
    runpod_pod.save_state(PodInfo("pod1", "203.0.113.7", 40122, "u"), cli_env["state"])
    res = CliRunner().invoke(app, ["pod", "down"])
    assert res.exit_code == 0, res.output
    assert cli_env["runpod"].terminated == ["pod1"]
    assert not cli_env["state"].exists()


def test_down_stale_state(cli_env):
    runpod_pod.save_state(PodInfo("gone", "h", 1, "u"), cli_env["state"])
    res = CliRunner().invoke(app, ["pod", "down"])
    assert res.exit_code == 0
    assert "no running pod" in res.output
    assert not cli_env["state"].exists()
    assert cli_env["runpod"].terminated == []


def test_ssh_command(cli_env):
    runpod_pod.save_state(PodInfo("pod1", "203.0.113.7", 40122, "u"), cli_env["state"])
    res = CliRunner().invoke(app, ["pod", "ssh"])
    assert res.exit_code == 0, res.output
    assert cli_env["remote"].calls == [remote.ssh_argv(
        PodInfo("pod1", "203.0.113.7", 40122, "u"))]


def test_ssh_no_pod(cli_env):
    res = CliRunner().invoke(app, ["pod", "ssh"])
    assert res.exit_code == 1
    assert "no running pod" in res.output


def test_batch_stale_state_says_no_pod(cli_env):
    runpod_pod.save_state(PodInfo("gone", "h", 1, "https://gone-8188.proxy.runpod.net"), cli_env["state"])
    scenes = cli_env["tmp"] / "s.yaml"
    scenes.write_text("scenes: []\n")
    res = CliRunner().invoke(app, ["batch", "face", str(scenes)])
    assert res.exit_code == 1
    assert "no running pod" in res.output and "cm pod up" in res.output
    assert not cli_env["state"].exists()


def test_create_kwargs_match_installed_sdk(fake, pubkey):
    """Guard against SDK drift: every kwarg we pass exists on the real runpod.create_pod."""
    import inspect

    import runpod as real_sdk

    runpod_pod.create(SETTINGS, Secrets(SECRET_VALUES), pubkey_path=pubkey)
    params = inspect.signature(real_sdk.create_pod).parameters
    assert set(fake.created[0]) <= set(params)
    for fn in ("get_pod", "terminate_pod"):
        assert callable(getattr(real_sdk, fn))


class RaisingRunpod(FakeRunpod):
    def __init__(self, message):
        super().__init__()
        self.api_key = "k"
        self.message = message

    def get_pod(self, pod_id):
        raise RuntimeError(self.message)


@pytest.mark.parametrize("message", ["Pod not found", "pod does not exist", "No pod with id abc", "NOT FOUND"])
def test_current_pod_not_found_error_clears_state(monkeypatch, tmp_path, message):
    monkeypatch.setattr(runpod_pod, "runpod", RaisingRunpod(message))
    state = tmp_path / "pod.json"
    runpod_pod.save_state(PodInfo("pod1", "h", 1, "u"), state)
    assert runpod_pod.exists("pod1") is False
    assert runpod_pod.current_pod(state) is None
    assert not state.exists()


def test_current_pod_other_error_keeps_state(monkeypatch, tmp_path):
    monkeypatch.setattr(runpod_pod, "runpod", RaisingRunpod("Something went wrong (500)"))
    state = tmp_path / "pod.json"
    runpod_pod.save_state(PodInfo("pod1", "h", 1, "u"), state)
    with pytest.raises(RuntimeError, match="500"):
        runpod_pod.current_pod(state)
    assert state.exists()


def test_save_state_keeps_created_at_for_same_pod(tmp_path):
    # `cm pod up` saves twice (after wait_ready and at the end); the pod-age guard of
    # `cm lora train` must see the first stamp, not the time bootstrap finished.
    state = tmp_path / "pod.json"
    info = PodInfo("pod1", "203.0.113.7", 40122, "u")
    runpod_pod.save_state(info, state)
    data = json.loads(state.read_text())
    data["created_at"] = "2026-10-14T08:00:00+00:00"
    state.write_text(json.dumps(data))
    runpod_pod.save_state(info, state)
    assert json.loads(state.read_text())["created_at"] == "2026-10-14T08:00:00+00:00"


def test_save_state_new_pod_gets_new_created_at(tmp_path):
    state = tmp_path / "pod.json"
    runpod_pod.save_state(PodInfo("old", "h", 1, "u"), state)
    data = json.loads(state.read_text())
    data["created_at"] = "2026-10-14T08:00:00+00:00"
    state.write_text(json.dumps(data))
    runpod_pod.save_state(PodInfo("new", "h", 1, "u"), state)
    data = json.loads(state.read_text())
    assert data["id"] == "new" and data["created_at"] != "2026-10-14T08:00:00+00:00"


def test_save_state_over_corrupt_file_writes_fresh(tmp_path):
    state = tmp_path / "pod.json"
    state.write_text("{not json")
    runpod_pod.save_state(PodInfo("pod1", "h", 1, "u"), state)
    assert json.loads(state.read_text())["id"] == "pod1"


# -- signals during `cm pod up` (closed terminal / kill) ----------------------

class _UnhandledSignal(BaseException):
    """Raised by the test's own handler: `cm pod up` did not install one."""


@pytest.fixture
def guard_signals():
    def unhandled(signum, frame):
        raise _UnhandledSignal(signum)

    saved = {s: signal.signal(s, unhandled) for s in (signal.SIGHUP, signal.SIGTERM)}
    yield unhandled
    for s, h in saved.items():
        signal.signal(s, h)


@pytest.mark.parametrize("sig", [signal.SIGHUP, signal.SIGTERM])
def test_up_signal_during_provisioning_terminates_pod(cli_env, monkeypatch, guard_signals, sig):
    def killed(pod_id, **kw):
        os.kill(os.getpid(), sig)
        raise AssertionError("signal did not interrupt")

    monkeypatch.setattr(runpod_pod, "wait_ready", killed)
    res = CliRunner().invoke(app, ["pod", "up"])
    assert not isinstance(res.exception, _UnhandledSignal), "no handler installed"
    assert res.exit_code == 1
    assert cli_env["runpod"].terminated == ["pod1"]
    assert not cli_env["state"].exists()
    assert sig.name in res.output
    # handlers restored after the command
    assert signal.getsignal(signal.SIGHUP) is guard_signals
    assert signal.getsignal(signal.SIGTERM) is guard_signals


def test_up_signal_during_rsync_terminates_pod(cli_env, monkeypatch, guard_signals):
    rem = cli_env["remote"]

    def run(argv):
        if argv[0] == "rsync":
            os.kill(os.getpid(), signal.SIGHUP)
        return rem(argv)

    monkeypatch.setattr(remote, "run", run)
    res = CliRunner().invoke(app, ["pod", "up"])
    assert not isinstance(res.exception, _UnhandledSignal), "no handler installed"
    assert res.exit_code == 1
    assert cli_env["runpod"].terminated == ["pod1"]


def test_up_success_restores_signal_handlers(cli_env, guard_signals):
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 0, res.output
    assert signal.getsignal(signal.SIGHUP) is guard_signals
    assert signal.getsignal(signal.SIGTERM) is guard_signals


def test_up_create_failure_mentions_stray_pod(cli_env, monkeypatch):
    def boom(**kw):
        raise RuntimeError("504 gateway timeout")

    monkeypatch.setattr(cli_env["runpod"], "create_pod", boom)
    res = CliRunner().invoke(app, ["pod", "up"])
    assert res.exit_code == 1
    assert "pod creation failed" in res.output
    assert "RunPod console" in res.output and "cm-comfyui" in res.output


def test_up_signal_during_create_mentions_stray_pod(cli_env, monkeypatch, guard_signals):
    def killed(**kw):
        os.kill(os.getpid(), signal.SIGTERM)
        raise AssertionError("signal did not interrupt")

    monkeypatch.setattr(cli_env["runpod"], "create_pod", killed)
    res = CliRunner().invoke(app, ["pod", "up"])
    assert not isinstance(res.exception, _UnhandledSignal), "no handler installed"
    assert res.exit_code == 1
    assert "cm-comfyui" in res.output
