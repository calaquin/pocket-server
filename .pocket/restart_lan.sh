#!/data/data/com.termux/files/usr/bin/sh
POCKET="/data/data/com.termux/files/home/.pocket"
STOP="$POCKET/stop_lan.sh"
START="$POCKET/start_lan.sh"
SLEEP="/data/data/com.termux/files/usr/bin/sleep"
TOAST="/data/data/com.termux/files/usr/bin/termux-toast"
"$STOP" >/dev/null 2>&1 || true
"$SLEEP" 0.3
"$START" >/dev/null 2>&1 || true
"$TOAST" "Pocket Server: Restarted"
