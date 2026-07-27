#!/usr/bin/env bash
# =============================================================================
# 构建 Octop 飞牛 FnOS 安装包 (.fpk)
#
# 双层 gzip tar 格式（与官方 fnos-hermes-agent 一致）：
#   外层 gzip(tar) 含: app.tgz, cmd/, config/, wizard/, ICON.PNG,
#                       ICON_256.PNG, LICENSE, manifest
#   内层 app.tgz    含: app/ 目录内容
#
# 用法（在仓库根目录执行）:
#   bash scripts/build-fpk.sh docker      # 构建 Docker 版  -> dist/octop-<ver>.fpk
#   bash scripts/build-fpk.sh native      # 构建本地版(非Docker) -> dist/octop-native-<ver>.fpk
#   bash scripts/build-fpk.sh             # 两个都构建
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist"

# 使用仓库内的临时目录，避免 Windows 风格 TMPDIR 在 Git Bash 下被错误解析
TMP="$(mktemp -d "$ROOT/.buildtmp.XXXXXX")"
cleanup() { rm -rf "$TMP" >/dev/null 2>&1 || true; }
trap cleanup EXIT

VER="$(grep -m1 '^version' "$ROOT/pyproject.toml" | sed -E 's/.*"([0-9][0-9.]*[0-9])".*/\1/')"
[ -n "$VER" ] || { echo "无法从 pyproject.toml 解析版本"; exit 1; }
echo "[build-fpk] Octop 版本: $VER"

mkdir -p "$OUT"

build_one() {
    local KIND="$1" PKG OUTNAME APP_INNER
    case "$KIND" in
        docker)
            PKG="$ROOT/fnos"
            OUTNAME="octop-$VER.fpk"
            APP_INNER="docker ui"
            ;;
        native)
            PKG="$ROOT/fnos-native"
            OUTNAME="octop-native-$VER.fpk"
            # 本地版：bin + ui；若 CI 已生成运行时则一并打包
            APP_INNER="bin ui"
            [ -d "$PKG/app/runtime" ] && APP_INNER="$APP_INNER runtime"
            ;;
        *) echo "未知类型: $KIND"; return 1 ;;
    esac

    local BUILD="$TMP/$KIND"
    rm -rf "$BUILD"; mkdir -p "$BUILD/cmd" "$BUILD/config" "$BUILD/wizard" "$BUILD/app"

    cp -r "$PKG/cmd/." "$BUILD/cmd/"
    cp -r "$PKG/config/." "$BUILD/config/"
    cp -r "$PKG/wizard/." "$BUILD/wizard/"
    cp -r "$PKG/app/." "$BUILD/app/"
    cp "$PKG/ICON.PNG" "$PKG/ICON_256.PNG" "$PKG/LICENSE" "$BUILD/"

    sed "s/^version = .*/version = $VER/" "$PKG/manifest" > "$BUILD/manifest"

    # 内层 app.tgz
    tar -czf "$BUILD/app.tgz" -C "$BUILD/app" $APP_INNER

    # 外层 .fpk
    tar -czf "$OUT/$OUTNAME" -C "$BUILD" \
        app.tgz cmd config wizard ICON.PNG ICON_256.PNG LICENSE manifest

    echo "[build-fpk] 产物: $OUT/$OUTNAME"
    echo "[build-fpk] 外层内容:"
    tar -tzf "$OUT/$OUTNAME"
}

if [ $# -eq 0 ]; then
    build_one docker
    build_one native
else
    for k in "$@"; do build_one "$k"; done
fi
