"""Settings (config/settings.yaml) and secrets (.env + environment)."""
from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Missing or invalid configuration."""


@dataclass(frozen=True)
class Settings:
    gpu_type: str
    datacenter: str
    image: str
    volume_gb: int
    idle_timeout_min: int
    max_runtime_h: float
    comfy_port: int
    remote_root: str


def load_settings(path: Path = Path("config/settings.yaml")) -> Settings:
    try:
        raw = yaml.safe_load(Path(path).read_text()) or {}
    except FileNotFoundError:
        raise ConfigError(f"settings file not found: {path}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping at top level")
    names = [f.name for f in fields(Settings)]
    missing = [n for n in names if n not in raw]
    if missing:
        raise ConfigError(f"{path}: missing setting(s): {', '.join(missing)}")
    unknown = sorted(set(raw) - set(names))
    if unknown:
        raise ConfigError(f"{path}: unknown setting(s): {', '.join(unknown)}")
    return Settings(**{n: raw[n] for n in names})


class Secrets(dict):
    """``dict[str, str]`` of secrets; ``require`` raises naming a missing key."""

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise ConfigError(f"missing secret {name}: set it in .env or the environment")
        return value


SECRET_KEYS = ("RUNPOD_API_KEY", "RUNPOD_VOLUME_ID", "HF_TOKEN")


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    return out


def load_secrets(env_path: Path = Path(".env")) -> Secrets:
    """Read ``.env`` then overlay real environment variables (env wins)."""
    secrets = Secrets(_parse_env_file(Path(env_path)))
    for key in SECRET_KEYS:
        if os.environ.get(key):
            secrets[key] = os.environ[key]
    return secrets
