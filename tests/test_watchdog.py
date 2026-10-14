import ast
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import comfy_model.watchdog as wd
from comfy_model.watchdog import comfy_busy, decide, run_loop, ssh_busy

MIN = 60.0
IDLE = 15 * MIN
MAXRT = 4 * 3600.0


def test_idle_after_timeout():
    assert decide(20 * MIN, 0, 0, False, IDLE, MAXRT) == "idle"
    assert decide(14 * MIN, 0, 0, False, IDLE, MAXRT) is None


def test_busy_resets_idle():
    # last busy at t=14min, now t=20min, timeout 15 -> no shutdown
    assert decide(20 * MIN, 0, 14 * MIN, False, IDLE, MAXRT) is None
    # currently busy never idles
    assert decide(60 * MIN, 0, 0, True, IDLE, MAXRT) is None


def test_max_runtime_wins_even_when_busy():
    assert decide(MAXRT, 0, MAXRT, True, IDLE, MAXRT) == "max_runtime"


def test_unreachable_comfy_is_not_busy():
    srv = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = srv.server_address[1]
    srv.server_close()  # nothing listening now
    assert comfy_busy(f"http://127.0.0.1:{port}") is False


def _serve(body: bytes):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_queue_parsing_busy():
    srv = _serve(json.dumps({"queue_running": [[1]], "queue_pending": []}).encode())
    try:
        assert comfy_busy(f"http://127.0.0.1:{srv.server_address[1]}") is True
    finally:
        srv.shutdown()
        srv.server_close()


def test_queue_parsing_empty_is_idle():
    srv = _serve(json.dumps({"queue_running": [], "queue_pending": []}).encode())
    try:
        assert comfy_busy(f"http://127.0.0.1:{srv.server_address[1]}") is False
    finally:
        srv.shutdown()
        srv.server_close()


def test_module_imports_only_stdlib():
    tree = ast.parse(Path(wd.__file__).read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import"
            mods.add((node.module or "").split(".")[0])
    assert mods
    assert mods <= set(sys.stdlib_module_names), mods - set(sys.stdlib_module_names)


def test_ssh_busy_heartbeat(tmp_path):
    f = tmp_path / "busy"
    assert ssh_busy(f, now=1000.0) is False  # missing
    f.write_text("x")
    import os

    os.utime(f, (900.0, 900.0))
    assert ssh_busy(f, now=1000.0) is True  # 100 s old
    assert ssh_busy(f, now=900.0 + 601) is False  # stale


def test_run_loop_terminates_idle_after_timeout_with_fake_clock():
    t = {"now": 1000.0}
    terminated = []

    def sleep(s):
        t["now"] += s

    reason = run_loop(
        now=lambda: t["now"],
        sleep=sleep,
        busy=lambda: False,
        terminate=terminated.append,
        idle_timeout_s=IDLE,
        max_runtime_s=MAXRT,
        poll_s=30,
    )
    assert reason == "idle"
    assert terminated == ["idle"]
    assert t["now"] - 1000.0 == IDLE


def test_run_loop_busy_defers_idle():
    t = {"now": 0.0}
    terminated = []
    # busy for first 10 min, then idle
    reason = run_loop(
        now=lambda: t["now"],
        sleep=lambda s: t.__setitem__("now", t["now"] + s),
        busy=lambda: t["now"] < 600,
        terminate=terminated.append,
        idle_timeout_s=IDLE,
        max_runtime_s=MAXRT,
        poll_s=30,
    )
    assert reason == "idle"
    assert t["now"] >= 600 + IDLE - 30


def test_main_without_pod_id_logs_and_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.delenv("RUNPOD_POD_ID", raising=False)
    monkeypatch.setattr(wd, "LOG_FILE", tmp_path / "sub" / "watchdog.log")
    assert wd.main() != 0
    assert "RUNPOD_POD_ID" in (tmp_path / "sub" / "watchdog.log").read_text()
