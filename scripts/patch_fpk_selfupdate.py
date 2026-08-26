#!/usr/bin/env python3
"""Apply the FPK online-upgrade support to an installed octop package.

Idempotent: safe to run multiple times (checks for the marker before each
patch). Usage:
    python3 patch_fpk_selfupdate.py <site-packages-dir>
e.g. python3 patch_fpk_selfupdate.py fnos-native/app/site-packages

The patch is applied to
`<site-packages>/octop/infra/setup/self_update.py`:

In FnOS FPK deployments the runtime loads octop from the app-center-managed
bundled site-packages (launcher sets PYTHONPATH to it), so a plain
`octop update` installs into the system Python — which the launcher never
loads — and a restart keeps the old version ("升级成功但重启无效"). The FPK
launcher exports `OCTOP_FPK_SITE_PACKAGES` pointing at that bundled directory;
this patch makes `run_upgrade()` install into that directory (pip --target)
so the new version is actually loaded after restart. Docker-compose
deployments are untouched (their online upgrade already installs into the
container environment and works on restart).
"""

from __future__ import annotations

import sys
from pathlib import Path

_MARKER = "OCTOP_FPK_SITE_PACKAGES"  # marker for the FPK upgrade branch

_TARGET_REL = Path("octop/infra/setup/self_update.py")

_OLD = (
    "def run_upgrade(*, verbose: bool = False) -> UpgradeResult:\n"
    "    installer = detect_installer()\n"
)

_NEW = """\
def get_version_in_dir(python_exe: str, target: str) -> str | None:
    \"\"\"Return the octop version installed in *target* (a ``pip --target`` dir).\"\"\"
    try:
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from importlib.metadata import version; print(version('octop'))"
        )
        result = subprocess.run(
            [python_exe, "-c", code, target],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception:
        pass
    return None


def _verify_fpk_upgrade(
    local_ver: str,
    site_packages: str,
    python_exe: str,
    mirror_errors: list[str],
) -> UpgradeResult:
    actual_ver: str | None = None
    for attempt in range(3):
        actual_ver = get_version_in_dir(python_exe, site_packages)
        if actual_ver and actual_ver != local_ver:
            break
        if attempt < 2:
            time.sleep(0.5)

    if actual_ver and is_newer(actual_ver, local_ver):
        return UpgradeResult(
            success=True,
            message=f"已升级到 {actual_ver}，请重启服务生效（应用中心托管的服务重启后加载新版）。",
            installed_version=actual_ver,
            mirror_errors=mirror_errors,
        )
    if actual_ver == local_ver:
        return UpgradeResult(
            success=False,
            error=(
                f"安装完成但版本仍为 {actual_ver}；"
                "请确认新版已发布，或改用飞牛应用中心安装新版 FPK。"
            ),
            installed_version=actual_ver,
            mirror_errors=mirror_errors,
        )
    return UpgradeResult(
        success=True,
        message="upgrade completed",
        installed_version=actual_ver,
        mirror_errors=mirror_errors,
    )


def _run_fpk_upgrade(site_packages: str, *, verbose: bool = False) -> UpgradeResult:
    \"\"\"FnOS FPK 部署下的在线升级：把新版安装到 launcher 实际加载的打包目录。

    launcher 通过 PYTHONPATH 从应用中心托管的打包 site-packages 加载 octop，
    在线安装到系统 Python 永远不会被加载（重启后仍是旧版）。本函数把新版
    安装到该打包目录本身，重启服务后即加载新版，升级真正生效。

    与普通部署不同，FPK 首次在线升级需要从零解析并下载完整依赖树
    （octop 依赖 orcakit-harness-agent 等大包），故超时显著放宽；且某镜像
    可能滞后（装到同版本旧版），此时继续尝试下一个镜像，最后以 pypi.org
    兜底，避免「镜像有货但版本不新」导致升级假成功。
    \"\"\"
    if not os.path.isdir(site_packages):
        return UpgradeResult(
            success=False,
            error=f"FPK site-packages 目录不存在：{site_packages}",
        )
    local_ver = get_local_version()
    mirror_errors: list[str] = []
    per_mirror_timeout = 900  # FPK 首次升级需下载完整依赖树，180s 不够

    def _run_install(cmd: list[str], label: str) -> tuple[int | None, str]:
        logger.debug("running %s: %s", label, " ".join(cmd))
        try:
            # NOCA:DangerousSubprocessUseAudit(argv list with shell=False; installer paths and mirrors are trusted)
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=not verbose,
                text=True,
                timeout=per_mirror_timeout,
            )
        except subprocess.TimeoutExpired:
            return None, f"timed out after {per_mirror_timeout}s"
        if result.returncode == 0:
            return 0, ""
        snippet = (result.stderr or result.stdout or "")[:300]
        return result.returncode, snippet

    python_exe = sys.executable
    installer = detect_installer()  # uv 优先：pip 对 orcakit-harness-agent[all] 依赖树解析会卡死

    def _build_cmd(index_url: str = "") -> list[str]:
        if installer == "uv":
            cmd = [
                find_uv_executable(),
                "pip",
                "install",
                "--python",
                python_exe,
                "--target",
                site_packages,
                "--upgrade-package",
                _PACKAGE_NAME,
            ]
            if index_url:
                cmd.extend(["--index-url", index_url])
            cmd.append(_PACKAGE_NAME)
            return cmd
        cmd = [
            python_exe,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--upgrade-strategy",
            "only-if-needed",
            "--target",
            site_packages,
        ]
        if index_url:
            cmd.extend(["-i", index_url])
        cmd.append(_PACKAGE_NAME)
        return cmd

    for mirror in _MIRRORS:
        rc, err_snippet = _run_install(_build_cmd(mirror), mirror)
        if rc != 0:
            mirror_errors.append(f"{mirror}: {err_snippet}")
            continue
        res = _verify_fpk_upgrade(local_ver, site_packages, python_exe, mirror_errors)
        if res.success:
            return res
        # 镜像装到了同版本/旧版（同步滞后）：继续尝试下一个镜像
        mirror_errors.append(f"{mirror}: {res.error or 'version unchanged'}")

    rc, err_snippet = _run_install(_build_cmd(), "pypi.org")
    if rc != 0:
        mirror_errors.append(f"pypi.org: {err_snippet or 'unknown error'}")
        return UpgradeResult(
            success=False,
            error="upgrade failed on all mirrors",
            mirror_errors=mirror_errors,
        )
    return _verify_fpk_upgrade(local_ver, site_packages, python_exe, mirror_errors)


def run_upgrade(*, verbose: bool = False) -> UpgradeResult:
    # [FPK] FnOS FPK 部署：launcher 通过 PYTHONPATH 从应用中心托管的打包
    # site-packages 加载 octop，在线安装到系统 Python 永远不会被加载（重启
    # 无效）。launcher 导出 OCTOP_FPK_SITE_PACKAGES 指向该打包目录，升级即
    # 安装到此目录并提示重启服务生效——升级真正可用，而非禁止升级。
    _fpk_site = os.environ.get("OCTOP_FPK_SITE_PACKAGES", "").strip()
    if _fpk_site:
        return _run_fpk_upgrade(_fpk_site, verbose=verbose)
    installer = detect_installer()
"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 patch_fpk_selfupdate.py <site-packages-dir>")
        return 2
    target = Path(sys.argv[1]) / _TARGET_REL
    if not target.is_file():
        print(f"[patch-fpk-selfupdate] target not found: {target}")
        return 1
    data = target.read_text(encoding="utf-8")
    if _MARKER in data:
        print("[patch-fpk-selfupdate] already patched, skip")
        return 0
    if _OLD not in data:
        print("[patch-fpk-selfupdate] pattern not found, abort (no changes)")
        return 1
    target.write_text(data.replace(_OLD, _NEW, 1), encoding="utf-8")
    print("[patch-fpk-selfupdate] FPK online-upgrade support applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
