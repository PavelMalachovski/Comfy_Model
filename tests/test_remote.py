from pathlib import Path

from comfy_model import remote
from comfy_model.runpod_pod import PodInfo

POD = PodInfo(id="abc123", ssh_host="203.0.113.7", ssh_port=40122,
              comfy_url="https://abc123-8188.proxy.runpod.net")

SSH_OPTS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "UserKnownHostsFile=.cm/known_hosts",
    "-o", "ConnectTimeout=15",
]


def test_ssh_argv():
    assert remote.ssh_argv(POD, "bash /workspace/cm/pod/bootstrap.sh") == [
        "ssh", *SSH_OPTS, "-p", "40122", "root@203.0.113.7",
        "bash /workspace/cm/pod/bootstrap.sh",
    ]


def test_ssh_argv_interactive_has_no_command():
    assert remote.ssh_argv(POD) == ["ssh", *SSH_OPTS, "-p", "40122", "root@203.0.113.7"]


def test_rsync_argv():
    argv = remote.rsync_argv(
        POD, [Path("pod/"), Path("workflows"), Path("src/comfy_model/watchdog.py")], "/workspace/cm/"
    )
    assert argv == [
        "rsync", "-az", "--exclude=__pycache__",
        "-e", "ssh " + " ".join(SSH_OPTS) + " -p 40122",
        "pod", "workflows", "src/comfy_model/watchdog.py",
        "root@203.0.113.7:/workspace/cm/",
    ]


def test_run_returns_exit_code():
    assert remote.run(["true"]) == 0
    assert remote.run(["false"]) == 1


def test_run_missing_binary_is_127(capsys):
    assert remote.run(["definitely-not-a-real-binary-xyz"]) == 127
    assert "definitely-not-a-real-binary-xyz" in capsys.readouterr().err
