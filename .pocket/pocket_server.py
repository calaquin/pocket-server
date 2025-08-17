from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse, PlainTextResponse
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import contextlib
import asyncio, os, time, json, subprocess, socket

LATEST_STATS = {}
LATEST_DEEP = {}
REFRESH_INTERVAL_SECS = int(os.getenv("POCKET_REFRESH_SECS", "30"))  # background refresh cadence

def run_cmd(cmd, timeout=3):
    """
    Run a shell command with a timeout.
    Returns stdout (str) on success, or None on error/timeout.
    """
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if res.returncode == 0:
            return res.stdout.strip()
        return None
    except Exception:
        return None

def get_basic_stats():
    return {
        "time": time.time(),
        "hostname": socket.gethostname(),
        "uptime": run_cmd("uptime"),
        "ips": run_cmd("ip -o -4 addr show | awk '{print $4}'"),
        "battery": run_cmd("termux-battery-status 2>/dev/null"),
        "storage": run_cmd("df -h /data 2>/dev/null"),
        "memory": run_cmd("cat /proc/meminfo | head -20"),
        "android": run_cmd("getprop ro.build.fingerprint"),
        "process": run_cmd("ps -o pid,ppid,stat,stime,cmd | head -20"),
    }

def get_deep_stats():
    return {
        "sensors": run_cmd("termux-sensor -l 1 2>/dev/null", timeout=5),
        "camera": run_cmd("termux-camera-info 2>/dev/null", timeout=5),
        "location": run_cmd("termux-location 2>/dev/null", timeout=8),
        "telephony": run_cmd("termux-telephony-deviceinfo 2>/dev/null", timeout=5),
        "wifi_scan": run_cmd("termux-wifi-scaninfo 2>/dev/null", timeout=8),
    }

async def stats(request):
    # manual refresh-on-demand
    global LATEST_STATS
    LATEST_STATS = get_basic_stats()
    return JSONResponse(LATEST_STATS)

async def stats_deep(request):
    # manual refresh-on-demand
    global LATEST_DEEP
    LATEST_DEEP = get_deep_stats()
    return JSONResponse(LATEST_DEEP)

NAV_HTML = """
<nav style='margin-bottom:1em;'>
  <a href='/'>Home</a> |
  <a href='/ui/overview'>Overview</a> |
  <a href='/ui/deep'>Deep Stats</a>
</nav>
"""

def kv_blocks(d):
    if not d:
        return "<p>Nothing yet.</p>"
    html = []
    for k, v in d.items():
        if v is None or v == "":
            v = "(no data)"
        html.append(
            f"

FILE="pocket_server.py"
BACKUP="pocket_server.$(date +%Y%m%d-%H%M%S).bak"

# 1) Backup existing file (if present)
[ -f "$FILE" ] && cp "$FILE" "$BACKUP" && echo "Backed up existing $FILE -> $BACKUP"

# 2) Write updated app
cat > "$FILE" <<'PY'
from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse, PlainTextResponse
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import contextlib
import asyncio, os, time, json, subprocess, socket

LATEST_STATS = {}
LATEST_DEEP = {}
REFRESH_INTERVAL_SECS = int(os.getenv("POCKET_REFRESH_SECS", "30"))  # background refresh cadence

def run_cmd(cmd, timeout=3):
    """
    Run a shell command with a timeout.
    Returns stdout (str) on success, or None on error/timeout.
    """
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        if res.returncode == 0:
            return res.stdout.strip()
        return None
    except Exception:
        return None

def get_basic_stats():
    return {
        "time": time.time(),
        "hostname": socket.gethostname(),
        "uptime": run_cmd("uptime"),
        "ips": run_cmd("ip -o -4 addr show | awk '{print $4}'"),
        "battery": run_cmd("termux-battery-status 2>/dev/null"),
        "storage": run_cmd("df -h /data 2>/dev/null"),
        "memory": run_cmd("cat /proc/meminfo | head -20"),
        "android": run_cmd("getprop ro.build.fingerprint"),
        "process": run_cmd("ps -o pid,ppid,stat,stime,cmd | head -20"),
    }

def get_deep_stats():
    return {
        "sensors": run_cmd("termux-sensor -l 1 2>/dev/null", timeout=5),
        "camera": run_cmd("termux-camera-info 2>/dev/null", timeout=5),
        "location": run_cmd("termux-location 2>/dev/null", timeout=8),
        "telephony": run_cmd("termux-telephony-deviceinfo 2>/dev/null", timeout=5),
        "wifi_scan": run_cmd("termux-wifi-scaninfo 2>/dev/null", timeout=8),
    }

async def stats(request):
    # manual refresh-on-demand
    global LATEST_STATS
    LATEST_STATS = get_basic_stats()
    return JSONResponse(LATEST_STATS)

async def stats_deep(request):
    # manual refresh-on-demand
    global LATEST_DEEP
    LATEST_DEEP = get_deep_stats()
    return JSONResponse(LATEST_DEEP)

NAV_HTML = """
<nav style='margin-bottom:1em;'>
  <a href='/'>Home</a> |
  <a href='/ui/overview'>Overview</a> |
  <a href='/ui/deep'>Deep Stats</a>
</nav>
"""

def kv_blocks(d):
    if not d:
        return "<p>Nothing yet.</p>"
    html = []
    for k, v in d.items():
        if v is None or v == "":
            v = "(no data)"
        html.append(
            f"<div style='border:1px solid #ccc;margin:6px 0;padding:8px;border-radius:8px;'>"
            f"<b>{k}</b><br><pre style='white-space:pre-wrap;margin:6px 0 0 0;'>{v}</pre></div>"
        )
    return "".join(html)

async def home(request):
    body = f"""
    {NAV_HTML}
    <h1>Pocket Server</h1>
    <p>Welcome! Use the links above to view stats.</p>
    <ul>
      <li><code>/stats</code> — fetch & return basic stats (JSON)</li>
      <li><code>/stats/deep</code> — fetch & return deep stats (JSON)</li>
      <li><code>/ui/overview</code> — cached basic stats (HTML)</li>
      <li><code>/ui/deep</code> — cached deep stats (HTML)</li>
      <li><code>/health</code> — simple health check</li>
    </ul>
    """
    return HTMLResponse(body)

async def ui_overview(request):
    html = NAV_HTML + "<h1>Overview</h1>"
    if not LATEST_STATS:
        html += "<p>No stats yet.</p>"
    else:
        html += kv_blocks(LATEST_STATS)
    html += """
    <p>
      <a href='/stats'>Refresh now (JSON)</a>
      &nbsp;|&nbsp;
      <a href='/ui/overview'>Reload page</a>
    </p>
    <small>Background refresh every {secs}s.</small>
    """.format(secs=REFRESH_INTERVAL_SECS)
    return HTMLResponse(html)

async def ui_deep(request):
    html = NAV_HTML + "<h1>Deep Stats</h1>"
    if not LATEST_DEEP:
        html += "<p>No deep stats yet.</p>"
    else:
        html += kv_blocks(LATEST_DEEP)
    html += """
    <p>
      <a href='/stats/deep'>Refresh now (JSON)</a>
      &nbsp;|&nbsp;
      <a href='/ui/deep'>Reload page</a>
    </p>
    <small>Background refresh every {secs}s.</small>
    """.format(secs=REFRESH_INTERVAL_SECS)
    return HTMLResponse(html)

async def health(request):
    return PlainTextResponse("ok")

async def _refresh_loop():
    """
    Background task that keeps the latest stats fresh for the UI pages.
    """
    global LATEST_STATS, LATEST_DEEP
    # prime caches quickly at boot
    try:
        LATEST_STATS = get_basic_stats()
    except Exception:
        pass
    try:
        LATEST_DEEP = get_deep_stats()
    except Exception:
        pass

    while True:
        try:
            LATEST_STATS = get_basic_stats()
        except Exception:
            pass
        # deep stats can be slower; alternate to avoid battery hammering
        await asyncio.sleep(REFRESH_INTERVAL_SECS // 2 or 1)
        try:
            LATEST_DEEP = get_deep_stats()
        except Exception:
            pass
        await asyncio.sleep(REFRESH_INTERVAL_SECS // 2 or 1)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(_refresh_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

routes = [
    Route("/", home),
    Route("/stats", stats),
    Route("/stats/deep", stats_deep),
    Route("/ui/overview", ui_overview),
    Route("/ui/deep", ui_deep),
    Route("/health", health),
]

app = Starlette(debug=True, routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
