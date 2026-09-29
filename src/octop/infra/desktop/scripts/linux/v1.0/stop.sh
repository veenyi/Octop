#!/bin/bash
set -euo pipefail

OCTOP_HOME="${OCTOP_HOME:-/root/.octop}"
DESKTOP_ENV="${OCTOP_HOME}/desktop/desktop.env"
if [ -f "$DESKTOP_ENV" ]; then
  # shellcheck disable=SC1090
  . "$DESKTOP_ENV"
fi
DISPLAY_NUM="${OCTOP_DESKTOP_DISPLAY:-:99}"
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  systemctl stop octop-desktop-openbox octop-desktop-session octop-desktop-xvnc || true
else
  INSTALL_ROOT="/opt/octop-desktop"
  pkill -f "openbox --config-file ${INSTALL_ROOT}/openbox.xml" 2>/dev/null || true
  pkill -f "xfce4-panel" 2>/dev/null || true
  pkill -f "xfdesktop" 2>/dev/null || true
  pkill -f "start-session.sh" 2>/dev/null || true
  pkill -f "Xvnc.*${DISPLAY_NUM}" 2>/dev/null || true
  pkill -f "Xtigervnc.*${DISPLAY_NUM}" 2>/dev/null || true
  rm -f "/tmp/.X${DISPLAY_NUM#:}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM#:}"
fi
echo "octop-desktop services stopped"
