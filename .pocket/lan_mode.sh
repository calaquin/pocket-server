#!/data/data/com.termux/files/usr/bin/sh
set -e

DISABLED="/data/data/com.termux/files/home/.pocket/.disabled"
if [ -f "$DISABLED" ]; then
  termux-notification --id pocket-lan \
    --title "Pocket Server: Disabled" \
    --content "Hosting is disabled. Tap Start to re-enable." \
    --priority low \
    --button1 "Start" --button1-action "/data/data/com.termux/files/home/.pocket/pocketctl start"
  exit 0
fi

BASE="/data/data/com.termux/files/home"
POCKET="$BASE/.pocket"
KNOWN="$POCKET/known_ssids"          # SSIDs or BSSIDs (one per line)
DISABLED="$POCKET/disabled"          # presence = do NOT autostart (manual stop)
SESS="pocket-caddy"
ROOT="$BASE/pocket"
PORT=8080

wifi_iface() {
  [ -f "$POCKET/iface_override" ] && { cat "$POCKET/iface_override"; return; }
  IF="$(getprop wifi.interface 2>/dev/null | tr -d '\r')"
  [ -n "$IF" ] && { echo "$IF"; return; }
  echo "wlan0"
}

lan_ip() {
  IP="$(termux-wifi-connectioninfo 2>/dev/null | jq -r '.ip // empty' || true)"
  echo "$IP" | grep -Eq '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' || IP=""
  IFACE="$(wifi_iface)"
  [ -z "$IP" ] && IP="$(getprop dhcp.${IFACE}.ipaddress 2>/dev/null)"
  [ -z "$IP" ] && IP="$(getprop dhcp.wlan0.ipaddress 2>/dev/null)"
  if [ -z "$IP" ] && command -v ifconfig >/dev/null 2>&1; then
    IP="$(ifconfig "$IFACE" 2>/dev/null | awk '/inet /{print $2; exit}')"
  fi
  printf "%s" "$IP"
}

wifi_identity() {
  INFO="$(termux-wifi-connectioninfo 2>/dev/null || true)"
  SSID="$(printf "%s" "$INFO" | jq -r '.ssid // empty')"
  BSSID="$(printf "%s" "$INFO" | jq -r '.bssid // empty')"
  [ -z "$SSID" ] && SSID="<unknown ssid>"
  echo "$SSID|$BSSID"
}

is_trusted() {
  [ -f "$KNOWN" ] || return 1
  IFS='|' read -r SSID BSSID <<EOF2
$(wifi_identity)
EOF2
  grep -Fxq "$SSID" "$KNOWN" && return 0
  [ -n "$BSSID" ] && grep -Fxq "$BSSID" "$KNOWN"
}

notify_on() {
  IP="$(lan_ip)"; IF="$(wifi_iface)"
  IFS='|' read -r SSID BSSID <<EOF2
$(wifi_identity)
EOF2
  /data/data/com.termux/files/usr/bin/termux-notification --id "pocket-lan" \
    --title "Pocket Server: LAN mode ON" \
    --content "SSID: $SSID  BSSID: ${BSSID:-?}  IF: $IF  URL: http://${IP:-unknown}:$PORT" \
    --priority high \
    --button1 "Open"    --button1-action "/data/data/com.termux/files/home/.pocket/pocketctl start" \
    --button2 "Stop"    --button2-action "/data/data/com.termux/files/home/.pocket/pocketctl stop" \
    --button3 "Restart" --button3-action "/data/data/com.termux/files/home/.pocket/pocketctl restart"
}

notify_off() {
  IFS='|' read -r SSID BSSID <<EOF2
$(wifi_identity)
EOF2
  /data/data/com.termux/files/usr/bin/termux-notification --id "pocket-lan" \
    --title "Pocket Server: LAN mode OFF" \
    --content "SSID '$SSID' (BSSID ${BSSID:-?}) — service stopped" \
    --priority low \
    --button1 "Start" --button1-action "/data/data/com.termux/files/home/.pocket/pocketctl start"
}

start_srv() {
  /data/data/com.termux/files/usr/bin/mkdir -p "$ROOT"
  [ -f "$ROOT/index.html" ] || /data/data/com.termux/files/usr/bin/printf '<h1>Pocket Server is alive (LAN mode)</h1>' > "$ROOT/index.html"
  if ! /data/data/com.termux/files/usr/bin/tmux has-session -t "$SESS" 2>/dev/null; then
    /data/data/com.termux/files/usr/bin/tmux new-session -d -s "$SESS" "/data/data/com.termux/files/usr/bin/caddy file-server --root $ROOT --listen :$PORT"
  fi
  notify_on
}

stop_srv() {
  if /data/data/com.termux/files/usr/bin/tmux has-session -t "$SESS" 2>/dev/null; then
    /data/data/com.termux/files/usr/bin/tmux kill-session -t "$SESS"
  fi
  notify_off
}

# --- Main: honor manual DISABLED flag first ---
if [ -f "$DISABLED" ]; then
  stop_srv
  exit 0
fi

if is_trusted; then
  start_srv
else
  stop_srv
fi
