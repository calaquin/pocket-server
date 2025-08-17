# Pocket Server (Android + Termux)

**Pocket Server** turns your Android phone into a toggleable personal server with:
- A friendly web UI (served by Caddy on `:8080`)
- An admin API (Starlette/Uvicorn on `:5201`)
- “Apps” you can enable/disable and retarget to custom ports
- “Serving” modes: **LAN** (exposed) and **LOCAL** (phone-only)

> Goal: Docker-like control for tinkerers, but phone-native and frictionless.

---

## Layout


---

## Quick Start

1. **Prereqs in Termux**
   ```bash
   pkg update
   pkg install -y termux-api tmux python caddy jq curl
   pip install --no-cache-dir starlette uvicorn==0.35.0


