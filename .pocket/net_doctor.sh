#!/data/data/com.termux/files/usr/bin/sh
set -eu
BIN="/data/data/com.termux/files/usr/bin"
HOME="/data/data/com.termux/files/home"

echo "=== Pocket Server Network Doctor ==="
echo "[serve_mode]"
mode="lan"; [ -f "$HOME/.pocket/.serve_mode" ] && mode="$(cat "$HOME/.pocket/.serve_mode" 2>/dev/null || echo lan)"
echo "mode=$mode"

echo
echo "[listeners on :8080]"
if command -v ss >/dev/null 2>&1; then
  ss -ltnp | grep ':8080' || echo "(nothing listening on 8080)"
else
  echo "(ss not available)"; netstat -ltnp 2>/dev/null | grep ':8080' || true
fi

echo
echo "[quick curls]"
echo "- curl 127.0.0.1:8080     ->" ; curl -sS -m 1 -I http://127.0.0.1:8080/       || true
echo "- curl 127.0.0.1:8080/ui  ->" ; curl -sS -m 1 -I http://127.0.0.1:8080/ui/overview || true
echo "- curl API /admin/status  ->" ; curl -sS -m 1     http://127.0.0.1:5201/admin/status || true

echo
echo "[tmux]"
tmux ls 2>/dev/null || echo "(no tmux sessions)"

echo
echo "[caddy logs tail]"
tail -n 20 "$HOME/.pocket/logs/pocket-caddy.log" 2>/dev/null || echo "(no caddy log)"

echo
echo "Tips:"
echo " - If mode=local, use http://127.0.0.1:8080 on the phone."
echo " - If you want LAN again:   ~/.pocket/pocketctl serve-start"
echo " - To enforce LOCAL only:   ~/.pocket/pocketctl serve-local"
echo
echo "Actions:"
echo " - Regenerate configs:      ~/.pocket/caddy_gen.sh"
echo " - Full restart:            ~/.pocket/pocketctl restart"
