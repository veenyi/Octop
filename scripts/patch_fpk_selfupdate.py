#!/usr/bin/env python3
"""Apply the FPK install-mode guard to an installed octop package.

Idempotent: safe to run multiple times (checks for the marker before each
patch). Usage:
    python3 patch_fpk_selfupdate.py <site-packages-dir>
e.g. python3 patch_fpk_selfupdate.py fnos-native/app/site-packages

The patch is applied to
`<site-packages>/octop/infra/setup/self_update.py`:

In FnOS FPK deployments the runtime loads octop from the app-center-managed
bundled site-packages (launcher sets PYTHONPATH to it), so `octop update` /
dashboard "立即升级" can never take effect: an online pip/uv install targets
the system Python (or the managed venv when one exists), which the launcher
never loads — after restart the bundled version still wins. The FPK launcher
/ docker-compose set `OCTOP_INSTALL_MODE=fpk-*`; this patch makes
`run_upgrade()` short-circuit with a clear guidance message so users upgrade
through the FnOS app center (new FPK) instead of a doomed in-app install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MARKER = "OCTOP_INSTALL_MODE"  # marker for the FPK guard

_TARGET_REL = Path("octop/infra/setup/self_update.py")

_OLD = (
    "def run_upgrade(*, verbose: bool = False) -> UpgradeResult:\n"
    "    installer = detect_installer()\n"
)

_NEW = (
    "def run_upgrade(*, verbose: bool = False) -> UpgradeResult:\n"
    "    # [FPK guard] FnOS FPK 部署下禁止内置在线升级：运行时从应用中心托管的\n"
    "    # 打包 site-packages 加载（PYTHONPATH），在线安装到系统 Python 永远无法\n"
    "    # 生效；升级请通过飞牛应用中心安装新版 FPK。launcher / docker-compose\n"
    "    # 设置 OCTOP_INSTALL_MODE=fpk-* 触发本分支。\n"
    "    _fpk_mode = os.environ.get(\"OCTOP_INSTALL_MODE\", \"\").lower()\n"
    "    if _fpk_mode.startswith(\"fpk\"):\n"
    "        return UpgradeResult(\n"
    "            success=False,\n"
    "            error=(\n"
    "                \"当前为飞牛 FPK 安装，内置在线升级不适用于本部署方式；\"\n"
    "                \"请在飞牛应用中心检查并安装新版 FPK 完成升级。\"\n"
    "            ),\n"
    "        )\n"
    "    installer = detect_installer()\n"
)


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
    print("[patch-fpk-selfupdate] FPK guard applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
