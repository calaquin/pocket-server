# Pocket Server (Android + Termux)

**Pocket Server** turns your Android phone into a toggleable personal server with:
- A friendly web UI (served by Caddy on `:8080`)
- An admin API (Starlette/Uvicorn on `:5201`)
- “Apps” you can enable/disable and retarget to custom ports
- “Serving” modes: **LAN** (exposed) and **LOCAL** (phone-only)

> Goal: Docker-like control for tinkerers, but phone-native and frictionless.

---

## Layout
pocket-server-src/
├── .pocket/ # scripts & runtime (kept local via .gitignore)
│ ├── pocketctl # service manager (start/stop, serve_on/off, restart)
│ ├── caddy_gen.sh # generates Caddyfile for LAN/LOCAL modes
│ ├── appctl # start/stop individual apps
│ ├── stats_starlette.py # admin API (Starlette/Uvicorn)
│ ├── logs/ # runtime logs (ignored)
│ ├── apps.example.json # sample registry (copy to apps.json to customize)
│ └── known_ssids.example # sample trusted SSIDs (copy to known_ssids)
└── pocket/ # web UI (served by Caddy)
├── index.html # Home (Hosting controls + Apps card)
└── apps/welcome/ # Example app (static site via python http.server)

---

## Quick Start

1. **Prereqs in Termux**
   ```bash
   pkg update
   pkg install -y termux-api tmux python caddy jq curl
   pip install --no-cache-dir starlette uvicorn==0.35.0


