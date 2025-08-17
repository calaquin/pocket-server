#!/data/data/com.termux/files/usr/bin/sh
POCKET="/data/data/com.termux/files/home/.pocket"
SESS_WEB="pocket-caddy"
SESS_API="pocket-stats"
ROOT="/data/data/com.termux/files/home/pocket"
TMUX="/data/data/com.termux/files/usr/bin/tmux"
CADDY="/data/data/com.termux/files/usr/bin/caddy"
MKDIR="/data/data/com.termux/files/usr/bin/mkdir"
PRINTF="/data/data/com.termux/files/usr/bin/printf"
TOAST="/data/data/com.termux/files/usr/bin/termux-toast"
CURL="/data/data/com.termux/files/usr/bin/curl"
LAN="$POCKET/lan_mode.sh"
LOGDIR="$POCKET/logs"

rm -f "$POCKET/disabled"
"$MKDIR" -p "$ROOT" "$LOGDIR"
[ -f "$ROOT/index.html" ] || "$PRINTF" '<h1>Pocket Server is alive (LAN mode)</h1>' > "$ROOT/index.html"

# Start stats API in its own tmux session
if ! "$TMUX" has-session -t "$SESS_API" 2>/dev/null; then
  "$TMUX" new-session -d -s "$SESS_API" "$POCKET/run_stats.sh"
  "$TMUX" pipe-pane -o -t "$SESS_API" "cat >> $LOGDIR/pocket-stats.log"
fi

# Start Caddy with Caddyfile
if ! "$TMUX" has-session -t "$SESS_WEB" 2>/dev/null; then
  "$TMUX" new-session -d -s "$SESS_WEB" "$CADDY run --config $ROOT/Caddyfile"
  "$TMUX" pipe-pane -o -t "$SESS_WEB" "cat >> $LOGDIR/pocket-caddy.log"
fi

"$TOAST" "Pocket Server: Started"

# quick health check
sleep 0.7
if "$CURL" -sS -m 1 http://127.0.0.1:5201/stats >/dev/null; then
  /data/data/com.termux/files/usr/bin/termux-notification --id "pocket-health" \
    --title "Pocket Server" --content "Stats API healthy on :5201" --priority low
else
  /data/data/com.termux/files/usr/bin/termux-notification --id "pocket-health" \
    --title "Pocket Server" --content "Stats API not responding — check logs" --priority low
fi

[ -x "$LAN" ] && "$LAN" >/dev/null 2>&1
