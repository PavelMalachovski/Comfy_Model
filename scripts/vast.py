"""Minimal vast.ai control for render sessions. The key comes from .env (VAST_API_KEY) and is never printed.

  python scripts/vast.py search [--gpu "RTX 5090"] [--max 0.9] [--ram 64]
  python scripts/vast.py create <offer_id> [--disk 150] [--label roxana]
  python scripts/vast.py wait <instance_id>        # waits for running, prints "host port"
  python scripts/vast.py status [<instance_id>]
  python scripts/vast.py destroy <instance_id>     # deletes instance and disk, then verifies it is gone

Only SFW tiers (instagram, social) are rendered on vast; Fanvue stays on the Mac (vast terms).
ComfyUI is reached through an SSH tunnel, no public port is opened.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://console.vast.ai/api/v0"
API1 = "https://console.vast.ai/api/v1"
IMAGE = os.environ.get("VAST_IMAGE", "pytorch/pytorch:2.8.0-cuda12.8-cudnn9-devel")


def key() -> str:
    k = os.environ.get("VAST_API_KEY")
    if not k:
        for line in Path(".env").read_text().splitlines():
            if line.startswith("VAST_API_KEY="):
                k = line.split("=", 1)[1].strip()
    if not k:
        sys.exit("VAST_API_KEY missing in .env")
    return k


def call(method: str, path: str, body=None, base=None):
    req = urllib.request.Request((base or API) + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"vast API {method} {path}: HTTP {e.code} {e.read()[:300]!r}")


def search(a):
    q = {"gpu_name": {"eq": a.gpu}, "num_gpus": {"eq": 1}, "rentable": {"eq": True}, "verified": {"eq": True},
         "reliability2": {"gte": 0.99}, "disk_space": {"gte": a.disk}, "inet_down": {"gte": 500},
         "cpu_ram": {"gte": a.ram * 1024}, "dph_total": {"lte": a.max}, "cuda_max_good": {"gte": 12.8},
         "type": "on-demand", "order": [["dph_total", "asc"]], "limit": 50}
    for o in call("POST", "/bundles/", q).get("offers", [])[:a.n]:
        print(f'{o["id"]:>10}  ${o["dph_total"]:.3f}/h  {o.get("geolocation", "?"):<22} rel {o["reliability2"]:.3f}  '
              f'down {int(o["inet_down"])}Mb  ram {int(o["cpu_ram"] / 1024)}GB  disk ${o.get("storage_cost", 0):.3f}/GB/mo')


def create(a):
    r = call("PUT", f"/asks/{a.offer}/", {"client_id": "me", "image": IMAGE, "disk": a.disk, "label": a.label,
                                          "runtype": "ssh_direct ssh_proxy", "onstart": "touch /root/.vast_ready"})
    if not r.get("success"):
        sys.exit(f"create failed: {r}")
    print(r["new_contract"])


def inst(i):
    return call("GET", f"/instances/{i}/").get("instances") or {}


def wait(a):
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        d = inst(a.id)
        st = d.get("actual_status")
        if st == "running" and d.get("ssh_host"):
            ports = d.get("ports") or {}
            direct = (ports.get("22/tcp") or [{}])[0].get("HostPort")
            if direct and d.get("public_ipaddr"):
                print(d["public_ipaddr"].strip(), direct)
            else:
                print(d["ssh_host"], d["ssh_port"])
            return
        print(f"  status {st} ({int(time.time() - t0)}s)", file=sys.stderr, flush=True)
        time.sleep(15)
    sys.exit("timeout waiting for instance")


def status(a):
    rows = [inst(a.id)] if a.id else call("GET", "/instances/", base=API1).get("instances", [])
    for d in rows:
        if d:
            print(d.get("id"), d.get("label"), d.get("gpu_name"), d.get("actual_status"),
                  f'${(d.get("dph_total") or 0):.3f}/h')
    if not any(rows):
        print("no instances")


def destroy(a):
    call("DELETE", f"/instances/{a.id}/", {})
    for _ in range(20):
        left = [d for d in call("GET", "/instances/", base=API1).get("instances", []) if d.get("id") == int(a.id)]
        if not left:
            print(f"instance {a.id} destroyed, verified gone")
            return
        time.sleep(5)
    sys.exit(f"instance {a.id} still listed after destroy, check console.vast.ai")


p = argparse.ArgumentParser()
sp = p.add_subparsers(dest="cmd", required=True)
s = sp.add_parser("search"); s.add_argument("--gpu", default="RTX 5090"); s.add_argument("--max", type=float, default=0.9)
s.add_argument("--ram", type=int, default=64); s.add_argument("--disk", type=int, default=150); s.add_argument("-n", type=int, default=8)
s.set_defaults(f=search)
s = sp.add_parser("create"); s.add_argument("offer"); s.add_argument("--disk", type=int, default=150)
s.add_argument("--label", default="roxana"); s.set_defaults(f=create)
s = sp.add_parser("wait"); s.add_argument("id"); s.add_argument("--timeout", type=int, default=900); s.set_defaults(f=wait)
s = sp.add_parser("status"); s.add_argument("id", nargs="?"); s.set_defaults(f=status)
s = sp.add_parser("destroy"); s.add_argument("id"); s.set_defaults(f=destroy)
a = p.parse_args()
a.f(a)
