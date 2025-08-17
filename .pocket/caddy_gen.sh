#!/data/data/com.termux/files/usr/bin/sh
set -eu
HOME="/data/data/com.termux/files/home"
REG="$HOME/.pocket/apps.json"
OUT_LAN="$HOME/pocket/Caddyfile.lan"
OUT_LOC="$HOME/pocket/Caddyfile.local"

mk_body(){
  mode="$1" # lan or local
  bind=":8080"
  [ "$mode" = "local" ] && bind="127.0.0.1:8080"

  {
    echo "$bind {"
    echo "  root * $HOME/pocket"
    echo "  encode zstd gzip"

    # API only
    cat <<'CFG'
  @api {
    path /stats*
    path /admin*
  }
  reverse_proxy @api 127.0.0.1:5201

  handle_path /ui/overview* {
    rewrite * /ui/overview.html
    file_server
  }
  handle_path /ui/deep* {
    rewrite * /ui/deep.html
    file_server
  }
CFG

    # Apps
    if [ -f "$REG" ]; then
      for app in $(jq -r 'keys[]' "$REG"); do
        enabled=$(jq -r --arg a "$app" '.[$a].enabled' "$REG")
        port=$(jq -r --arg a "$app" '.[$a].port' "$REG")
        path=$(jq -r --arg a "$app" '.[$a].path' "$REG")

        if [ "$enabled" = "true" ]; then
          # App-specific static settings page fallback (so it loads even if backend is down)
          if [ "$app" = "welcome" ]; then
            echo "  handle ${path}/settings.html {"
            echo "    root * $HOME/pocket/apps/welcome"
            echo "    file_server"
            echo "  }"
          fi

          echo "  handle_path ${path}* {"
          echo "    reverse_proxy 127.0.0.1:${port}"
          echo "  }"
        fi
      done
    fi

    echo "  file_server"
    echo "}"
  } > "$2"
}

mk_body lan   "$OUT_LAN"
mk_body local "$OUT_LOC"

MODE="lan"; [ -f "$HOME/.pocket/.serve_mode" ] && MODE="$(cat "$HOME/.pocket/.serve_mode" 2>/dev/null || echo lan)"
cp "$HOME/pocket/Caddyfile.$MODE" "$HOME/pocket/Caddyfile" 2>/dev/null || true
