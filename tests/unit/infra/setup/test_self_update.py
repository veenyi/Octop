"""Tests for octop.infra.setup.self_update."""

from __future__ import annotations

import pytest

from octop.infra.setup.self_update import (
    build_upgrade_command,
    is_newer,
    is_prerelease,
    parse_version,
    pick_latest_versions,
)


def test_pep440_order() -> None:
    assert parse_version("0.9.34a1") < parse_version("0.9.34b1")
    assert parse_version("0.9.34b1") < parse_version("0.9.34rc1")
    assert parse_version("0.9.34rc1") < parse_version("0.9.34")
    assert parse_version("0.9.34-beta.1") == parse_version("0.9.34b1")
    assert parse_version("0.7.2") > parse_version("0.7.1")


def test_is_prerelease() -> None:
    assert is_prerelease("0.9.34b1")
    assert is_prerelease("0.9.34-beta.1")
    assert is_prerelease("0.9.34rc1")
    assert is_prerelease("0.9.34a1")
    assert is_prerelease("0.9.34.dev1")
    assert not is_prerelease("0.9.34")
    assert not is_prerelease("0.7.1")


def test_is_newer() -> None:
    assert is_newer("0.7.2", "0.7.1")
    assert not is_newer("0.7.1", "0.7.2")
    assert not is_newer("0.7.1", "0.7.1")
    assert is_newer("0.9.34", "0.9.34b1")
    assert is_newer("0.9.34b1", "0.9.33")
    assert not is_newer("0.9.34b1", "0.9.34")


def test_pick_latest_versions_splits_stable_and_pre() -> None:
    latest_any, latest_stable = pick_latest_versions(["0.9.33", "0.9.34b1", "0.9.32", "0.9.34a1"])
    assert latest_any == "0.9.34b1"
    assert latest_stable == "0.9.33"


def test_pick_latest_versions_all_prerelease() -> None:
    latest_any, latest_stable = pick_latest_versions(["0.9.34b1", "0.9.34a1"])
    assert latest_any == "0.9.34b1"
    assert latest_stable is None


def test_build_upgrade_command_prerelease_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    python = "/home/user/.octop/venv/bin/python"
    uv_cmd = build_upgrade_command("uv", python, allow_prerelease=True, version="0.9.34b1")
    assert uv_cmd is not None
    assert uv_cmd[uv_cmd.index("--prerelease") + 1] == "allow"
    assert "octop==0.9.34b1" in uv_cmd
    monkeypatch.setattr("octop.infra.setup.self_update.has_pip", lambda _: True)
    pip_cmd = build_upgrade_command("pip", python, allow_prerelease=True, version="0.9.34b1")
    assert pip_cmd is not None
    assert "--pre" in pip_cmd
    assert "octop==0.9.34b1" in pip_cmd


def test_build_upgrade_command_pins_stable_without_pre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    python = "/home/user/.octop/venv/bin/python"
    uv_cmd = build_upgrade_command("uv", python, version="0.9.33")
    assert uv_cmd is not None
    assert "octop==0.9.33" in uv_cmd
    assert "--prerelease" not in uv_cmd
    monkeypatch.setattr("octop.infra.setup.self_update.has_pip", lambda _: True)
    pip_cmd = build_upgrade_command("pip", python, version="0.9.33")
    assert pip_cmd is not None
    assert "octop==0.9.33" in pip_cmd
    assert "--pre" not in pip_cmd
