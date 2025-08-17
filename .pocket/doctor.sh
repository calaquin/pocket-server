#!/data/data/com.termux/files/usr/bin/sh
set -e
echo "=== Pocket Server Doctor (API-first) ==="
echo "[binaries]"
for x in termux-notification tmux caddy python ifconfig timeout curl uvicorn; do
  printf " - %-18s %s\n" "$x:" "$(command -v "$x" 2>/dev/null || echo MISSING)"
done
echo
echo "[wifi.identity]"
termux-wifi-connectioninfo 2>/dev/null | jq '{ssid,bssid,ip}' || echo "(no wifi info)"
echo
echo "[tmux sessions]"
tmux ls 2>/dev/null || echo "(no tmux sessions)"
echo
echo "[processes]"
ps -A | grep -E 'uvicorn|caddy|tmux' | sed 's/^/  /' || true
echo
echo "[api health]"
curl -sS -m 1 http://127.0.0.1:5201/stats      >/dev/null && echo " /stats: OK"      || echo " /stats: FAIL"
curl -sS -m 2 http://127.0.0.1:5201/stats/deep >/dev/null && echo " /stats/deep: OK" || echo " /stats/deep: FAIL"
echo "=== end ==="
