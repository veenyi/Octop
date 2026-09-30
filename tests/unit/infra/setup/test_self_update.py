"""Tests for octop.infra.setup.self_update."""

from __future__ import annotations

from pathlib import Path

import pytest

from octop.infra.setup.self_update import is_newer, parse_version


def test_parse_version_ignores_suffix() -> None:
    assert parse_version("0.7.2") > parse_version("0.7.1")
    assert parse_version("0.7.1rc1") == parse_version("0.7.1")


def test_is_newer() -> None:
    assert is_newer("0.7.2", "0.7.1")
    assert not is_newer("0.7.1", "0.7.2")
    assert not is_newer("0.7.1", "0.7.1")


# --- FPK uv bootstrap + manifest version refresh ------------------------------


def test_bootstrap_uv_short_circuits_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    import octop.infra.setup.self_update as su

    monkeypatch.setattr(su, "detect_installer", lambda: "uv")
    monkeypatch.setattr(su, "find_uv_executable", lambda: "/usr/local/bin/uv")
    assert su.bootstrap_uv() == "/usr/local/bin/uv"


def test_bootstrap_uv_installs_via_first_mirror(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    import octop.infra.setup.self_update as su

    calls: list[list[str]] = []
    monkeypatch.setattr(su, "find_uv_executable", lambda: "/home/u/.local/bin/uv")
    states = iter(["pip", "uv", "uv", "uv", "uv", "uv", "uv"])
    monkeypatch.setattr(su, "detect_installer", lambda: next(states))

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(su.subprocess, "run", fake_run)
    assert su.bootstrap_uv() == "/home/u/.local/bin/uv"
    assert calls and "--user" in calls[0]
    assert calls[0][calls[0].index("-i") + 1] == su._MIRRORS[0]


def test_bootstrap_uv_returns_none_when_all_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    import octop.infra.setup.self_update as su

    monkeypatch.setattr(su, "detect_installer", lambda: "pip")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "boom")

    monkeypatch.setattr(su.subprocess, "run", fake_run)
    assert su.bootstrap_uv() is None


def test_refresh_fpk_manifest_version_rewrites_version_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    import octop.infra.setup.self_update as su

    manifest = tmp_path / "manifest"
    manifest.write_text("appname=octop-native\nversion=0.9.28\n", encoding="utf-8")
    monkeypatch.setattr(su, "_fpk_manifest_path", lambda: manifest)
    seen: dict[str, object] = {}

    def fake_run(cmd, input=None, **kwargs):
        seen["cmd"] = cmd
        seen["input"] = input
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(su.subprocess, "run", fake_run)
    assert su.refresh_fpk_manifest_version("1.0.2b5") is True
    assert seen["cmd"][:3] == ["sudo", "-n", "tee"]
    text = str(seen["input"])
    assert "version=1.0.2b5" in text
    assert "version=0.9.28" not in text
    assert "appname=octop-native" in text


def test_refresh_fpk_manifest_version_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import octop.infra.setup.self_update as su

    manifest = tmp_path / "manifest"
    manifest.write_text("appname=octop-native\nversion=1.0.2b5\n", encoding="utf-8")
    monkeypatch.setattr(su, "_fpk_manifest_path", lambda: manifest)

    def fail_run(*args, **kwargs):
        raise AssertionError("must not write when version already synced")

    monkeypatch.setattr(su.subprocess, "run", fail_run)
    assert su.refresh_fpk_manifest_version("1.0.2b5") is True


def test_refresh_fpk_manifest_version_no_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    import octop.infra.setup.self_update as su

    monkeypatch.setattr(su, "_fpk_manifest_path", lambda: None)
    assert su.refresh_fpk_manifest_version("1.0.2b5") is False
