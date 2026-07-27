#!/usr/bin/env bash
# =============================================================================
# 构建 Octop 飞牛 FnOS 安装包 (.fpk)
#
# 采用与官方 fnos-hermes-agent 一致的「双层 gzip tar」格式：
#   外层 gzip(tar) 含: app.tgz, cmd/, config/, wizard/, ICON.PNG,
#                       ICON_256.PNG, LICENSE, manifest
#   内层 app.tgz    含: app/ 目录内容（docker/ + ui/）
#
# 用法（在仓库根目录执行）:
#   bash scripts/build-fpk.sh
# 产物: dist/octop-<version>.fpk
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="$ROOT/fnos"
OUT="$ROOT/dist"

# 使用仓库内的临时目录，避免 Windows 风格 TMPDIR 在 Git Bash 下被错误解析
TMP="$(mktemp -d "$ROOT/.buildtmp.XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

# 从仓库根 pyproject.toml 读取版本号
VER="$(grep -m1 '^version' "$ROOT/pyproject.toml" | sed -E 's/.*"([0-9][0-9.]*[0-9])".*/\1/')"
[ -n "$VER" ] || { echo "无法从 pyproject.toml 解析版本"; exit 1; }
echo "[build-fpk] Octop 版本: $VER"

# 复制包内容到临时目录（避免直接改动仓库内的 fnos/）
mkdir -p "$TMP/cmd" "$TMP/config" "$TMP/wizard" "$TMP/app"
cp -r "$PKG/cmd/." "$TMP/cmd/"
cp -r "$PKG/config/." "$TMP/config/"
cp -r "$PKG/wizard/." "$TMP/wizard/"
cp -r "$PKG/app/." "$TMP/app/"
cp "$PKG/ICON.PNG" "$PKG/ICON_256.PNG" "$PKG/LICENSE" "$TMP/"

# 将版本注入 manifest（不修改仓库内文件）
sed "s/^version = .*/version = $VER/" "$PKG/manifest" > "$TMP/manifest"

# 构建内层 app.tgz（app/ 目录下所有内容，无 app/ 前缀，无 ./ 前缀）
tar -czf "$TMP/app.tgz" -C "$TMP/app" docker ui

mkdir -p "$OUT"

# 构建外层 .fpk（扁平顶层）
tar -czf "$OUT/octop-$VER.fpk" -C "$TMP" \
    app.tgz cmd config wizard ICON.PNG ICON_256.PNG LICENSE manifest

echo "[build-fpk] 产物: $OUT/octop-$VER.fpk"
ls -la "$OUT/octop-$VER.fpk"

echo "[build-fpk] 外层内容:"
tar -tzf "$OUT/octop-$VER.fpk"
echo "[build-fpk] 内层 app.tgz 内容:"
tar -xzOf "$OUT/octop-$VER.fpk" app.tgz | tar -tz
