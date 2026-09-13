"""Bind address resolution for `octop run`: CLI flag > env > config.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from octop.cli.commands.run import resolve_bind


@pytest.fixture
def octop_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OCTOP_HOME", str(tmp_path))
    monkeypatch.delenv("OCTOP_PORT", raising=False)
    monkeypatch.delenv("OCTOP_BIND_HOST", raising=False)
    return tmp_path


def _write_config(home: Path, **data: object) -> None:
    (home / "config.json").write_text(json.dumps(data), encoding="utf-8")


def test_no_config_no_env(octop_home: Path) -> None:
    assert resolve_bind(None, None) == (None, None)


def test_config_file_values(octop_home: Path) -> None:
    _write_config(octop_home, bind_host="127.0.0.1", port=8088)
    assert resolve_bind(None, None) == ("127.0.0.1", 8088)


def test_env_overrides_config_file(octop_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(octop_home, bind_host="127.0.0.1", port=8088)
    monkeypatch.setenv("OCTOP_PORT", "9001")
    monkeypatch.setenv("OCTOP_BIND_HOST", "0.0.0.0")
    assert resolve_bind(None, None) == ("0.0.0.0", 9001)


def test_cli_flags_win_over_env_and_file(octop_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(octop_home, bind_host="127.0.0.1", port=8088)
    monkeypatch.setenv("OCTOP_PORT", "9001")
    assert resolve_bind("10.0.0.1", 7777) == ("10.0.0.1", 7777)


def test_invalid_env_port_falls_back_to_file(
    octop_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(octop_home, port=8088)
    monkeypatch.setenv("OCTOP_PORT", "not-a-number")
    assert resolve_bind(None, None) == (None, 8088)


def test_legacy_host_key(octop_home: Path) -> None:
    _write_config(octop_home, host="192.168.1.10", port=1234)
    assert resolve_bind(None, None) == ("192.168.1.10", 1234)
