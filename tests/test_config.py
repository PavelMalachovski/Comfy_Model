from pathlib import Path

import pytest

from comfy_model.config import ConfigError, load_secrets, load_settings


def test_settings_defaults_load():
    s = load_settings()
    assert s.idle_timeout_min == 15 and s.max_runtime_h == 4
    assert s.gpu_type == "NVIDIA GeForce RTX 4090"
    assert s.datacenter == "EU-RO-1"
    assert "cuda12.8" in s.image
    assert s.volume_gb == 100
    assert s.comfy_port == 8188
    assert s.remote_root == "/workspace"


def test_settings_missing_key_names_it(tmp_path: Path):
    p = tmp_path / "s.yaml"
    p.write_text("gpu_type: x\n")
    with pytest.raises(ConfigError, match="datacenter"):
        load_settings(p)


def test_secrets_from_env_file_and_env(tmp_path: Path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nRUNPOD_API_KEY=abc\nHF_TOKEN='quoted'\n\n")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("RUNPOD_VOLUME_ID", "vol1")
    secrets = load_secrets(env)
    assert secrets["RUNPOD_API_KEY"] == "abc"
    assert secrets["HF_TOKEN"] == "quoted"
    assert secrets["RUNPOD_VOLUME_ID"] == "vol1"


def test_env_overrides_file(tmp_path: Path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("HF_TOKEN=fromfile\n")
    monkeypatch.setenv("HF_TOKEN", "fromenv")
    assert load_secrets(env)["HF_TOKEN"] == "fromenv"


def test_require_missing_names_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    secrets = load_secrets(tmp_path / "nope.env")
    with pytest.raises(ConfigError, match="RUNPOD_API_KEY"):
        secrets.require("RUNPOD_API_KEY")


def test_require_empty_value_is_missing(tmp_path: Path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("RUNPOD_API_KEY=\n")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="RUNPOD_API_KEY"):
        load_secrets(env).require("RUNPOD_API_KEY")
