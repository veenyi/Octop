#!/bin/bash
set -euo pipefail

# Honor the display/port chosen at install time (persisted in desktop.env)
# instead of hardcoding :99/5900.
OCTOP_HOME="${OCTOP_HOME:-/root/.octop}"
DESKTOP_ENV="${OCTOP_HOME}/desktop/desktop.env"
if [ -f "$DESKTOP_ENV" ]; then
  # shellcheck disable=SC1090
  . "$DESKTOP_ENV"
fi
DISPLAY_NUM="${OCTOP_DESKTOP_DISPLAY:-:99}"
VNC_PORT="${OCTOP_DESKTOP_VNC_PORT:-5900}"

_xvnc_alive() {
  local pattern="$1"
  local pid stat
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    stat="$(ps -o stat= -p "$pid" 2>/dev/null || true)"
    [[ "$stat" == Z* ]] && continue
    return 0
  done < <(pgrep -f "$pattern" 2>/dev/null || true)
  return 1
}

if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  for unit in octop-desktop-xvnc octop-desktop-session octop-desktop-openbox; do
    if [ ! -f "/etc/systemd/system/${unit}.service" ]; then
      echo "systemd unit ${unit}.service is missing; re-run the desktop install" >&2
      exit 1
    fi
  done
  systemctl daemon-reload
  systemctl start octop-desktop-xvnc octop-desktop-session octop-desktop-openbox
else
  OCTOP_HOME="${OCTOP_HOME:-$HOME/.octop}"
  INSTALL_ROOT="/opt/octop-desktop"
  if ! _xvnc_alive "Xvnc.*${DISPLAY_NUM}"; then
    rm -f "/tmp/.X${DISPLAY_NUM#:}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM#:}"
    nohup "$(command -v Xvnc || command -v Xtigervnc)" "${DISPLAY_NUM}" -depth 24 -geometry 1920x1080 -dpi 96 \
      -rfbport "${VNC_PORT}" -localhost yes -AlwaysShared -maxclients 256 -SecurityTypes VncAuth \
      -rfbauth /etc/octop-desktop/rfbauth \
      > "${OCTOP_HOME}/desktop/xvnc.log" 2>&1 &
    sleep 1
  fi
  if ! _xvnc_alive "openbox --config-file ${INSTALL_ROOT}/openbox.xml"; then
    nohup "${INSTALL_ROOT}/start-session.sh" > "${OCTOP_HOME}/desktop/session.log" 2>&1 &
    sleep 1
    nohup "${INSTALL_ROOT}/start-openbox.sh" > "${OCTOP_HOME}/desktop/openbox.log" 2>&1 &
    sleep 1
  fi
fi
echo "octop-desktop services started"
