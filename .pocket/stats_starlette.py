import os, json, time, shutil, subprocess, re
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

BIN   = "/data/data/com.termux/files/usr/bin"
HOME  = "/data/data/com.termux/files/home"
POCKET= os.path.join(HOME, ".pocket")
SNAP  = os.path.join(POCKET, "deep_snapshot.json")

def run(cmd, timeout=2.0, text=True):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout, text=text)
        return (out.stdout or "").strip()
    except Exception:
        return ""

def try_json(cmd, timeout=2.0):
    try:
        out = run(cmd, timeout=timeout)
        return json.loads(out) if out else {}
    except Exception:
        return {}

def private_ip(ip):
    return bool(ip) and (ip.startswith("10.") or ip.startswith("192.168.") or any(ip.startswith(f"172.{i}.") for i in range(16,32)))

def uptime_seconds():
    try:
        with open("/proc/uptime","r") as f: return float(f.read().split()[0])
    except Exception: return 0.0

def _wifi():
    info = try_json(f"{BIN}/termux-wifi-connectioninfo")
    ip = info.get("ip"); ip = ip if private_ip(ip or "") else ""
    if not ip:
        for iface in ("wlan0","wlan1","wifi0","wl0"):
            ip = run(f"{BIN}/ifconfig {iface} 2>/dev/null | awk '/inet /{{print $2; exit}}'")
            if private_ip(ip): break
    ips=set()
    if ip: ips.add(ip)
    lines = run(f"""{BIN}/ifconfig 2>/dev/null | awk '/flags=/{{gsub(/:/,"",$1); i=$1}} $1=="inet" && i!="lo" {{print $2}}'""")
    for line in lines.splitlines():
        if private_ip(line): ips.add(line)
    return {"ssid": info.get("ssid"), "bssid": info.get("bssid"), "rssi": info.get("rssi"), "ip": ip, "ips": sorted(ips)}

def _android():
    return {
        "brand": run("getprop ro.product.brand"),
        "model": run("getprop ro.product.model"),
        "device": run("getprop ro.product.device"),
        "android": run("getprop ro.build.version.release"),
        "sdk": run("getprop ro.build.version.sdk"),
        "security_patch": run("getprop ro.build.version.security_patch"),
        "fingerprint": run("getprop ro.build.fingerprint"),
        "kernel": run("uname -r"),
        "selinux": run("getenforce") or "unknown",
    }

def _storage():
    total, used, free = shutil.disk_usage(os.path.expanduser("~"))
    return {"total": total, "used": used, "free": free}

def _battery():
    return try_json(f"{BIN}/termux-battery-status") or {}

def _memory():
    d={}
    try:
        with open("/proc/meminfo","r") as f:
            for line in f:
                k,v = line.split(":",1); d[k.strip()]=v.strip()
    except Exception: pass
    return d

def _services():
    out = run(f"{BIN}/tmux ls 2>/dev/null")
    sess = {line.split(":")[0] for line in out.splitlines() if line.strip()}
    return {"caddy": "running" if "pocket-caddy" in sess else "stopped",
            "stats": "running" if "pocket-stats" in sess else "stopped"}

def deep_payload():
    def sensor_list():
        s = run(f"{BIN}/termux-sensor -l", timeout=2.0)
        return [line.strip() for line in s.splitlines() if line.strip()] or []
    def sensor_read(sample_names=None):
        common = ["accelerometer","gyroscope","magnetic_field","ambient_temperature","light","proximity",
                  "pressure","relative_humidity","gravity","linear_acceleration","rotation_vector",
                  "geomagnetic_rotation_vector","game_rotation_vector","orientation","heart_rate","step_counter"]
        names = sample_names or common
        have=set(); lst=sensor_list()
        for name in names:
            for line in lst:
                if name in line:
                    have.add(line.split(":")[0]); break
        if not have: return {}
        sel=",".join(sorted(have))
        j = try_json(f"{BIN}/termux-sensor -n 1 -s {sel}", timeout=3.0)
        out={}
        if isinstance(j,dict):
            for k,v in j.items():
                out[k] = v.get("values") if isinstance(v,dict) and "values" in v else v
        return out
    def location():
        net = try_json(f"{BIN}/termux-location -p network", timeout=2.5)
        gps = try_json(f"{BIN}/termux-location -p gps", timeout=3.5)
        return {"network": net, "gps": gps}
    def telephony():
        dev = try_json(f"{BIN}/termux-telephony-deviceinfo", timeout=2.0)
        cells = try_json(f"{BIN}/termux-telephony-cellinfo", timeout=2.0)
        return {"device": dev or {}, "cells": cells or {}}
    def camera():
        return try_json(f"{BIN}/termux-camera-info", timeout=2.0) or {}
    def audio_io():
        tts = run(f"{BIN}/termux-tts-engines", timeout=2.0)
        return {"tts_engines": [x.strip() for x in tts.splitlines() if x.strip()]}
    def torch_ir():
        feat = run("pm list features 2>/dev/null | grep -q 'feature:android.hardware.consumerir' && echo yes || echo no", timeout=1.5)
        if feat != "yes":
            return {"ir_supported": False, "ir_freqs": None, "note": "no consumer IR feature"}
        data = try_json(f"{BIN}/termux-infrared-frequencies", timeout=2.0)
        return {"ir_supported": True, "ir_freqs": data.get("frequencies") if isinstance(data, dict) else None}
    def brightness():
        for p in ("/sys/class/backlight/panel0-backlight/brightness",
                  "/sys/class/leds/lcd-backlight/brightness"):
            if os.path.exists(p):
                try:
                    with open(p,"r") as f: val=f.read().strip()
                    maxp = p.replace("/brightness","/max_brightness")
                    maxv=None
                    if os.path.exists(maxp):
                        with open(maxp,"r") as f: maxv=f.read().strip()
                    return {"path": p, "value": val, "max": maxv}
                except Exception: pass
        return {}
    def thermals():
        base="/sys/class/thermal"
        try:
            if not os.path.isdir(base): return []
            out=[]
            for name in os.listdir(base):
                if not name.startswith("thermal_zone"): continue
                z=os.path.join(base,name)
                tpath=os.path.join(z,"temp"); ypath=os.path.join(z,"type")
                if not os.path.exists(tpath): continue
                try:
                    with open(tpath,"r") as f: raw=f.read().strip()
                    typ=""
                    try:
                        with open(ypath,"r") as f: typ=f.read().strip()
                    except Exception: pass
                    tempC=None
                    if re.fullmatch(r"-?\d+", raw):
                        v=int(raw); tempC = v/1000.0 if abs(v)>1000 else v/10.0
                    else:
                        try: tempC=float(raw)
                        except: tempC=None
                    out.append({"zone":name,"type":typ,"tempC":tempC,"raw":raw})
                except PermissionError:
                    continue
                except Exception:
                    continue
            return out
        except PermissionError:
            return {"error":"permission_denied"}
        except Exception:
            return []
    def clipboard_meta():
        txt = run(f"{BIN}/termux-clipboard-get", timeout=1.0)
        return {"text_len": len(txt) if txt else 0}
    return {
        "time": int(time.time()),
        "wifi": _wifi(),
        "ips": _wifi().get("ips", []),
        "location": location(),
        "sensors": {"list": sensor_list(), "sample": sensor_read()},
        "telephony": telephony(),
        "camera": camera(),
        "audio": audio_io(),
        "torch_ir": torch_ir(),
        "brightness": brightness(),
        "thermals": thermals(),
        "battery": _battery(),
        "storage": _storage(),
        "memory": _memory(),
        "cpu": {"count": os.cpu_count()},
        "android": _android(),
        "services": _services(),
        "clipboard": clipboard_meta(),
        "notes": "Deep stats captured on demand to save power."
    }

_cache = {}
TTLS = {"network":60, "device":3600, "system":120, "battery":30, "services":10}

def _get(name):
    now = time.time()
    ts, data = _cache.get(name, (0, None))
    ttl = TTLS[name]
    if data is not None and (now - ts) < ttl:
        return {"_cached_at": int(ts), **data}
    if name == "network":
        v = _wifi()
    elif name == "device":
        v = _android()
    elif name == "system":
        v = {"storage": _storage(), "memory": _memory(), "cpu": {"count": os.cpu_count()}, "uptime_sec": uptime_seconds()}
    elif name == "battery":
        v = _battery()
    else:
        v = _services()
    _cache[name] = (now, v)
    return {"_cached_at": int(now), **v}

def _refresh(name):
    _cache.pop(name, None)
    return _get(name)

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

async def health(_): return JSONResponse({"ok": True})
async def stats(_request):
    return JSONResponse({
        "time": int(time.time()),
        "network":  _get("network"),
        "device":   _get("device"),
        "system":   _get("system"),
        "battery":  _get("battery"),
        "services": _get("services"),
    })
async def refresh_group(request):
    grp = request.query_params.get("group","").strip().lower()
    if grp not in TTLS:
        return JSONResponse({"ok": False, "error": "unknown_group", "groups": list(TTLS.keys())}, status_code=400)
    data = _refresh(grp)
    return JSONResponse({"ok": True, "group": grp, "data": data})
async def stats_deep(_): return JSONResponse(deep_payload())
async def post_snapshot(_):
    os.makedirs(POCKET, exist_ok=True)
    data = deep_payload()
    data["_snapshot_saved_at"] = int(time.time())
    with open(SNAP, "w") as f:
        json.dump(data, f)
    return JSONResponse({"ok": True, "saved_at": data["_snapshot_saved_at"], "path": SNAP})
async def get_snapshot(_):
    if not os.path.exists(SNAP):
        return JSONResponse({"error":"no_snapshot"}, status_code=404)
    with open(SNAP,"r") as f:
        data = json.load(f)
    return JSONResponse(data)

app = Starlette(routes=[
    Route("/health", health),
    Route("/stats", stats),
    Route("/stats/refresh", refresh_group, methods=["POST"]),
    Route("/stats/deep", stats_deep),
    Route("/stats/deep/snapshot", post_snapshot, methods=["POST"]),
    Route("/stats/deep/snapshot", get_snapshot,  methods=["GET"]),
])

# ----- Admin endpoints (simple, no auth on LAN; add auth later) -----
def _run_sh(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=4)
        return out.returncode, (out.stdout or "").strip(), (out.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

async def admin_status(_):
    code,out,err = _run_sh(f"{HOME}/.pocket/pocketctl status")
    try:
        data = json.loads(out) if out else {}
    except Exception:
        data = {"raw": out, "error": err}
    return JSONResponse({"ok": code==0, "services": data})

async def admin_start(_):
    code,out,err = _run_sh(f"{HOME}/.pocket/pocketctl start")
    return JSONResponse({"ok": code==0, "stdout": out, "stderr": err})

async def admin_stop(_):
    code,out,err = _run_sh(f"{HOME}/.pocket/pocketctl stop")
    return JSONResponse({"ok": code==0, "stdout": out, "stderr": err})

# register routes
from starlette.routing import Route as _R
app.routes.extend([
    _R("/admin/status", admin_status),
    _R("/admin/start",  admin_start, methods=["POST"]),
    _R("/admin/stop",   admin_stop,  methods=["POST"]),
])

# ----- Admin: serving + enable/disable + shutdown -----
def _run_sh(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return out.returncode, (out.stdout or "").strip(), (out.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

async def admin_status(_):
    code,out,err = _run_sh(f"{HOME}/.pocket/pocketctl status")
    try:
        data = json.loads(out) if out else {}
    except Exception:
        data = {"raw": out, "error": err}
    return JSONResponse({"ok": code==0, "services": data})

async def admin_start(_):   return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl start")[0]==0})
async def admin_stop(_):    return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl stop")[0]==0})
async def admin_srv_on(_):  return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl serve-start")[0]==0})
async def admin_srv_off(_): return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl serve-stop")[0]==0})
async def admin_enable(_):  return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl enable")[0]==0})
async def admin_disable(_): return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl disable")[0]==0})
async def admin_shutdown(_):
    # stop hosting + disable
    _run_sh(f"{HOME}/.pocket/pocketctl stop")
    return JSONResponse({"ok": True})

from starlette.routing import Route as _R
app.routes.extend([
    _R("/admin/status",   admin_status),
    _R("/admin/start",    admin_start,    methods=["POST"]),
    _R("/admin/stop",     admin_stop,     methods=["POST"]),
    _R("/admin/serve_on", admin_srv_on,   methods=["POST"]),
    _R("/admin/serve_off",admin_srv_off,  methods=["POST"]),
    _R("/admin/enable",   admin_enable,   methods=["POST"]),
    _R("/admin/disable",  admin_disable,  methods=["POST"]),
    _R("/admin/shutdown", admin_shutdown, methods=["POST"]),
])

# ----- Admin: serving + enable/disable + shutdown -----
def _run_sh(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return out.returncode, (out.stdout or "").strip(), (out.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

async def admin_status(_):
    code,out,err = _run_sh(f"{HOME}/.pocket/pocketctl status")
    try:
        data = json.loads(out) if out else {}
    except Exception:
        data = {"raw": out, "error": err}
    return JSONResponse({"ok": code==0, "services": data})

async def admin_start(_):   return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl start")[0]==0})
async def admin_stop(_):    return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl stop")[0]==0})
async def admin_srv_on(_):  return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl serve-start")[0]==0})
async def admin_srv_off(_): return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl serve-stop")[0]==0})
async def admin_enable(_):  return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl enable")[0]==0})
async def admin_disable(_): return JSONResponse({"ok": _run_sh(f"{HOME}/.pocket/pocketctl disable")[0]==0})
async def admin_shutdown(_):
    # stop hosting + disable
    _run_sh(f"{HOME}/.pocket/pocketctl stop")
    return JSONResponse({"ok": True})

from starlette.routing import Route as _R
app.routes.extend([
    _R("/admin/status",   admin_status),
    _R("/admin/start",    admin_start,    methods=["POST"]),
    _R("/admin/stop",     admin_stop,     methods=["POST"]),
    _R("/admin/serve_on", admin_srv_on,   methods=["POST"]),
    _R("/admin/serve_off",admin_srv_off,  methods=["POST"]),
    _R("/admin/enable",   admin_enable,   methods=["POST"]),
    _R("/admin/disable",  admin_disable,  methods=["POST"]),
    _R("/admin/shutdown", admin_shutdown, methods=["POST"]),
])

# ----- Apps admin -----
def _run_sh(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=6)
        return out.returncode, (out.stdout or "").strip(), (out.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

APPS_REG = os.path.join(POCKET, "apps.json")

def _load_apps():
    try:
        with open(APPS_REG,"r") as f: return json.load(f)
    except Exception: return {}

def _save_apps(d):
    with open(APPS_REG,"w") as f: json.dump(d, f, indent=2)

async def apps_list(_):
    return JSONResponse({"apps": _load_apps()})

async def app_toggle(request):
    app = request.path_params.get("app")
    q = request.query_params
    enabled = q.get("enabled")
    if enabled is None: return JSONResponse({"ok": False, "error":"missing_enabled"}, status_code=400)
    enabled = True if enabled.lower()=="true" else False
    apps = _load_apps()
    if app not in apps: return JSONResponse({"ok": False, "error":"unknown_app"}, status_code=404)
    apps[app]["enabled"] = enabled
    _save_apps(apps)
    _run_sh(f"{HOME}/.pocket/appctl {'start' if enabled else 'stop'} {app}")
    _run_sh(f"{HOME}/.pocket/pocketctl app-reload")
    return JSONResponse({"ok": True, "apps": apps})

async def app_port(request):
    app = request.path_params.get("app")
    body = await request.json()
    try:
        port = int(body.get("port"))
    except Exception:
        return JSONResponse({"ok": False, "error":"invalid_port"}, status_code=400)
    apps = _load_apps()
    if app not in apps: return JSONResponse({"ok": False, "error":"unknown_app"}, status_code=404)
    apps[app]["port"] = port
    _save_apps(apps)
    # restart app if enabled
    if apps[app].get("enabled", False):
        _run_sh(f"{HOME}/.pocket/appctl restart {app}")
    _run_sh(f"{HOME}/.pocket/pocketctl app-reload")
    return JSONResponse({"ok": True, "apps": apps})

# routes
from starlette.routing import Route as _R
app.routes.extend([
    _R("/apps",            apps_list),
    _R("/apps/{app}/toggle", app_toggle, methods=["POST"]),
    _R("/apps/{app}/port",   app_port,   methods=["POST"]),
])

# ----- Apps admin -----
def _run_sh(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=6)
        return out.returncode, (out.stdout or "").strip(), (out.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

APPS_REG = os.path.join(POCKET, "apps.json")

def _load_apps():
    try:
        with open(APPS_REG,"r") as f: return json.load(f)
    except Exception: return {}

def _save_apps(d):
    with open(APPS_REG,"w") as f: json.dump(d, f, indent=2)

async def apps_list(_):
    return JSONResponse({"apps": _load_apps()})

async def app_toggle(request):
    app = request.path_params.get("app")
    q = request.query_params
    enabled = q.get("enabled")
    if enabled is None: return JSONResponse({"ok": False, "error":"missing_enabled"}, status_code=400)
    enabled = True if enabled.lower()=="true" else False
    apps = _load_apps()
    if app not in apps: return JSONResponse({"ok": False, "error":"unknown_app"}, status_code=404)
    apps[app]["enabled"] = enabled
    _save_apps(apps)
    _run_sh(f"{HOME}/.pocket/appctl {'start' if enabled else 'stop'} {app}")
    _run_sh(f"{HOME}/.pocket/pocketctl app-reload")
    return JSONResponse({"ok": True, "apps": apps})

async def app_port(request):
    app = request.path_params.get("app")
    body = await request.json()
    try:
        port = int(body.get("port"))
    except Exception:
        return JSONResponse({"ok": False, "error":"invalid_port"}, status_code=400)
    apps = _load_apps()
    if app not in apps: return JSONResponse({"ok": False, "error":"unknown_app"}, status_code=404)
    apps[app]["port"] = port
    _save_apps(apps)
    # restart app if enabled
    if apps[app].get("enabled", False):
        _run_sh(f"{HOME}/.pocket/appctl restart {app}")
    _run_sh(f"{HOME}/.pocket/pocketctl app-reload")
    return JSONResponse({"ok": True, "apps": apps})

# routes
from starlette.routing import Route as _R
app.routes.extend([
    _R("/apps",            apps_list),
    _R("/apps/{app}/toggle", app_toggle, methods=["POST"]),
    _R("/apps/{app}/port",   app_port,   methods=["POST"]),
])

# ----- Apps admin -----
def _run_sh(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=6)
        return out.returncode, (out.stdout or "").strip(), (out.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

APPS_REG = os.path.join(POCKET, "apps.json")

def _load_apps():
    try:
        with open(APPS_REG,"r") as f: return json.load(f)
    except Exception: return {}

def _save_apps(d):
    with open(APPS_REG,"w") as f: json.dump(d, f, indent=2)

async def apps_list(_):
    return JSONResponse({"apps": _load_apps()})

async def app_toggle(request):
    app = request.path_params.get("app")
    q = request.query_params
    enabled = q.get("enabled")
    if enabled is None: return JSONResponse({"ok": False, "error":"missing_enabled"}, status_code=400)
    enabled = True if enabled.lower()=="true" else False
    apps = _load_apps()
    if app not in apps: return JSONResponse({"ok": False, "error":"unknown_app"}, status_code=404)
    apps[app]["enabled"] = enabled
    _save_apps(apps)
    _run_sh(f"{HOME}/.pocket/appctl {'start' if enabled else 'stop'} {app}")
    _run_sh(f"{HOME}/.pocket/pocketctl app-reload")
    return JSONResponse({"ok": True, "apps": apps})

async def app_port(request):
    app = request.path_params.get("app")
    body = await request.json()
    try:
        port = int(body.get("port"))
    except Exception:
        return JSONResponse({"ok": False, "error":"invalid_port"}, status_code=400)
    apps = _load_apps()
    if app not in apps: return JSONResponse({"ok": False, "error":"unknown_app"}, status_code=404)
    apps[app]["port"] = port
    _save_apps(apps)
    # restart app if enabled
    if apps[app].get("enabled", False):
        _run_sh(f"{HOME}/.pocket/appctl restart {app}")
    _run_sh(f"{HOME}/.pocket/pocketctl app-reload")
    return JSONResponse({"ok": True, "apps": apps})

# routes
from starlette.routing import Route as _R
app.routes.extend([
    _R("/apps",            apps_list),
    _R("/apps/{app}/toggle", app_toggle, methods=["POST"]),
    _R("/apps/{app}/port",   app_port,   methods=["POST"]),
])

# ----- Apps admin -----
def _run_sh(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=6)
        return out.returncode, (out.stdout or "").strip(), (out.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)

APPS_REG = os.path.join(POCKET, "apps.json")

def _load_apps():
    try:
        with open(APPS_REG,"r") as f: return json.load(f)
    except Exception: return {}

def _save_apps(d):
    with open(APPS_REG,"w") as f: json.dump(d, f, indent=2)

async def apps_list(_):
    return JSONResponse({"apps": _load_apps()})

async def app_toggle(request):
    app = request.path_params.get("app")
    q = request.query_params
    enabled = q.get("enabled")
    if enabled is None: return JSONResponse({"ok": False, "error":"missing_enabled"}, status_code=400)
    enabled = True if enabled.lower()=="true" else False
    apps = _load_apps()
    if app not in apps: return JSONResponse({"ok": False, "error":"unknown_app"}, status_code=404)
    apps[app]["enabled"] = enabled
    _save_apps(apps)
    _run_sh(f"{HOME}/.pocket/appctl {'start' if enabled else 'stop'} {app}")
    _run_sh(f"{HOME}/.pocket/pocketctl app-reload")
    return JSONResponse({"ok": True, "apps": apps})

async def app_port(request):
    app = request.path_params.get("app")
    body = await request.json()
    try:
        port = int(body.get("port"))
    except Exception:
        return JSONResponse({"ok": False, "error":"invalid_port"}, status_code=400)
    apps = _load_apps()
    if app not in apps: return JSONResponse({"ok": False, "error":"unknown_app"}, status_code=404)
    apps[app]["port"] = port
    _save_apps(apps)
    # restart app if enabled
    if apps[app].get("enabled", False):
        _run_sh(f"{HOME}/.pocket/appctl restart {app}")
    _run_sh(f"{HOME}/.pocket/pocketctl app-reload")
    return JSONResponse({"ok": True, "apps": apps})

# routes
from starlette.routing import Route as _R
app.routes.extend([
    _R("/apps",            apps_list),
    _R("/apps/{app}/toggle", app_toggle, methods=["POST"]),
    _R("/apps/{app}/port",   app_port,   methods=["POST"]),
])

# === Pocket Server: Admin endpoint to change Welcome app port ===
from starlette.responses import JSONResponse
import json, os, subprocess

APPS_REG = os.path.expanduser("~/.pocket/apps.json")

def _read_apps():
    if not os.path.exists(APPS_REG):
        return {}
    with open(APPS_REG, "r") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def _write_apps(data):
    os.makedirs(os.path.dirname(APPS_REG), exist_ok=True)
    with open(APPS_REG, "w") as f:
        json.dump(data, f, indent=2)

def _is_port_ok(p):
    try:
        p = int(p)
        return 1024 <= p <= 65535
    except Exception:
        return False

@app.route("/admin/app/welcome/port", methods=["POST"])
async def admin_app_welcome_port(request):
    body = await request.json()
    port = body.get("port")
    if not _is_port_ok(port):
        return JSONResponse({"ok": False, "error": "invalid_port"}, status_code=400)

    # 1) Update apps.json
    apps = _read_apps()
    apps.setdefault("welcome", {"enabled": True, "port": 5210, "path": "/apps/welcome"})
    apps["welcome"]["port"] = int(port)
    _write_apps(apps)

    # 2) Restart the app on the new port
    try:
        subprocess.run(
            ["/data/data/com.termux/files/home/.pocket/appctl", "restart", "welcome"],
            check=True,
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"app_restart_failed: {e}"}, status_code=500)

    # 3) Regenerate and reload Caddy routing to the new port
    try:
        subprocess.run(
            ["/data/data/com.termux/files/home/.pocket/pocketctl", "app-reload"],
            check=True,
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"caddy_reload_failed: {e}"}, status_code=500)

    return JSONResponse({"ok": True, "port": int(port)})

# === Pocket Server: Welcome app meta (current port) ===
from starlette.responses import JSONResponse
import json, os

APPS_REG = os.path.expanduser("~/.pocket/apps.json")

def _apps_read():
    if not os.path.exists(APPS_REG):
        return {}
    try:
        with open(APPS_REG, "r") as f:
            return json.load(f)
    except Exception:
        return {}

@app.route("/admin/app/welcome/meta", methods=["GET"])
async def admin_app_welcome_meta(request):
    apps = _apps_read()
    w = apps.get("welcome", {})
    return JSONResponse({
        "ok": True,
        "enabled": bool(w.get("enabled", True)),
        "port": int(w.get("port", 5210)),
        "path": w.get("path", "/apps/welcome")
    })

# === Pocket Server: Welcome app meta (current port) ===
from starlette.responses import JSONResponse
import json, os

APPS_REG = os.path.expanduser("~/.pocket/apps.json")

def _apps_read():
    if not os.path.exists(APPS_REG):
        return {}
    try:
        with open(APPS_REG, "r") as f:
            return json.load(f)
    except Exception:
        return {}

@app.route("/admin/app/welcome/meta", methods=["GET"])
async def admin_app_welcome_meta(request):
    apps = _apps_read()
    w = apps.get("welcome", {})
    return JSONResponse({
        "ok": True,
        "enabled": bool(w.get("enabled", True)),
        "port": int(w.get("port", 5210)),
        "path": w.get("path", "/apps/welcome")
    })

# === Pocket Server: Welcome app toggle enable/disable ===
from starlette.responses import JSONResponse
import json, os, subprocess

APPS_REG = os.path.expanduser("~/.pocket/apps.json")

def _apps_read():
    if not os.path.exists(APPS_REG): return {}
    try:
        with open(APPS_REG,"r") as f: return json.load(f)
    except Exception: return {}

def _apps_write(d):
    os.makedirs(os.path.dirname(APPS_REG), exist_ok=True)
    with open(APPS_REG,"w") as f: json.dump(d, f, indent=2)

@app.route("/admin/app/welcome/toggle", methods=["POST"])
async def admin_app_welcome_toggle(request):
    enabled = request.query_params.get("enabled","").lower() in ("1","true","yes","on")
    apps = _apps_read()
    w = apps.setdefault("welcome", {"enabled": True, "port": 5210, "path": "/apps/welcome"})
    w["enabled"] = enabled
    _apps_write(apps)
    try:
        if enabled:
            subprocess.run([os.path.expanduser("~/.pocket/appctl"), "start", "welcome"], check=True)
        else:
            subprocess.run([os.path.expanduser("~/.pocket/appctl"), "stop", "welcome"], check=True)
        subprocess.run([os.path.expanduser("~/.pocket/pocketctl"), "app-reload"], check=True)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return JSONResponse({"ok": True, "enabled": enabled})
