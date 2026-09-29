"""Tests for display/VNC-port persistence in octop.infra.desktop.setup."""

from __future__ import annotations

from pathlib import Path

import pytest

from octop.infra.desktop import setup as desktop_setup


def _write_env(tmp_path: Path, text: str) -> Path:
    env_file = tmp_path / "desktop.env"
    env_file.write_text(text, encoding="utf-8")
    return env_file


def test_display_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path, "export DISPLAY=:100\nexport OCTOP_DESKTOP_DISPLAY=:100\n")
    monkeypatch.setattr(desktop_setup, "desktop_env_file", lambda: env_file)
    assert desktop_setup._display_from_env_file() == ":100"


def test_vnc_port_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path, "export DISPLAY=:100\nexport OCTOP_DESKTOP_VNC_PORT=5901\n")
    monkeypatch.setattr(desktop_setup, "desktop_env_file", lambda: env_file)
    assert desktop_setup._vnc_port_from_env_file() == 5901


def test_vnc_port_missing_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path, "export DISPLAY=:99\n")
    monkeypatch.setattr(desktop_setup, "desktop_env_file", lambda: env_file)
    assert desktop_setup._vnc_port_from_env_file() is None


def test_write_geometry_env_persists_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = _write_env(
        tmp_path,
        "export DISPLAY=:100\nexport OCTOP_DESKTOP_DISPLAY=:100\nexport OCTOP_DESKTOP_VNC_PORT=5901\n",
    )
    monkeypatch.setattr(desktop_setup, "desktop_env_file", lambda: env_file)
    desktop_setup._write_geometry_env("1920x1080")
    text = env_file.read_text(encoding="utf-8")
    assert "export DISPLAY=:100" in text
    assert "export OCTOP_DESKTOP_VNC_PORT=5901" in text
    assert "export OCTOP_DESKTOP_GEOMETRY=1920x1080" in text


def test_write_geometry_env_without_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = _write_env(tmp_path, "export DISPLAY=:99\n")
    monkeypatch.setattr(desktop_setup, "desktop_env_file", lambda: env_file)
    desktop_setup._write_geometry_env("1280x720")
    text = env_file.read_text(encoding="utf-8")
    assert "OCTOP_DESKTOP_VNC_PORT" not in text


def test_xvnc_service_active_uses_configured_display(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = _write_env(tmp_path, "export OCTOP_DESKTOP_DISPLAY=:100\n")
    monkeypatch.setattr(desktop_setup, "desktop_env_file", lambda: env_file)
    monkeypatch.delenv("OCTOP_DESKTOP_DISPLAY", raising=False)
    seen: dict[str, object] = {}

    class _Result:
        returncode = 0

    def fake_run(cmd: list[str], **kwargs: object) -> _Result:
        seen["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(desktop_setup.subprocess, "run", fake_run)
    assert desktop_setup._xvnc_service_active() is True
    cmd = seen["cmd"]
    assert isinstance(cmd, list) and cmd[0] == "pgrep"
    assert cmd[2] == "X(vnc|tigervnc).*:100"
