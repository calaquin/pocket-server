#!/data/data/com.termux/files/usr/bin/sh
POCKET="/data/data/com.termux/files/home/.pocket"
SESS_WEB="pocket-caddy"
SESS_API="pocket-stats"
TMUX="/data/data/com.termux/files/usr/bin/tmux"
PKILL="/data/data/com.termux/files/usr/bin/pkill"
TOAST="/data/data/com.termux/files/usr/bin/termux-toast"
LAN="$POCKET/lan_mode.sh"

echo "1" > "$POCKET/disabled"

"$TMUX" has-session -t "$SESS_WEB" 2>/dev/null && "$TMUX" kill-session -t "$SESS_WEB"
"$TMUX" has-session -t "$SESS_API" 2>/dev/null && "$TMUX" kill-session -t "$SESS_API"
"$PKILL" -f "caddy file-server" 2>/dev/null || true
"$PKILL" -f "uvicorn .*stats_starlette:app" 2>/dev/null || true

"$TOAST" "Pocket Server: Stopped"
[ -x "$LAN" ] && "$LAN" >/dev/null 2>&1
