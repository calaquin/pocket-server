#!/data/data/com.termux/files/usr/bin/sh
# Run the Starlette stats API on 127.0.0.1:5201

PY="/data/data/com.termux/files/usr/bin/python"
POCKET="/data/data/com.termux/files/home/.pocket"
APP="stats_starlette:app"

cd "$POCKET" || exit 1
# Ensure PYTHONPATH includes the pocket folder
PYTHONPATH="$POCKET${PYTHONPATH:+:$PYTHONPATH}" \
exec "$PY" -m uvicorn --host 127.0.0.1 --port 5201 "$APP"
