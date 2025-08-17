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
            got = run(f"{BIN}/ifconfig {iface} 2>/dev/null | awk '/inet /{{print $2; exit}}'")
            if private_ip(got): ip = got; break
    ips=set()
    if ip: ips.add(ip)
    lines = run(f"""{BIN}/ifconfig 2>/dev/null | awk '/flags=/{{gsub(/:/,"",$1); i=$1}} $1=="inet" && i!="lo" {{print $2}}'""")
    for line in lines.splitlines():
        if private_ip(line): ips.add(line)
    return {"ssid": info.get("ssid"), "bssid": info.get("bssid"), "rssi": info.get("rssi"), "ip": ip, "ips": sorted(ips)}

def _android():
    gp = lambda k: run(f"getprop {k}")
    return {"brand": gp("ro.product.brand"), "model": gp("ro.product.model"), "device": gp("ro.product.device"),
            "android": gp("ro.build.version.release"), "sdk": gp("ro.build.version.sdk"),
            "security_patch": gp("ro.build.version.security_patch"), "fingerprint": gp("ro.build.fingerprint"),
            "kernel": run("uname -r")}

def _storage():
    total, used, free = shutil.disk_usage(os.path.expanduser("~"))
    return {"total": total, "used": used, "free": free}

def _battery():  return try_json(f"{BIN}/termux-battery-status") or {}
def _memory():
    d={}
    try:
        with open("/proc/meminfo","r") as f:
            for line in f: k,v = line.split(":",1); d[k.strip()]=v.strip()
    except Exception: pass
    return d
def _services():
    out = run(f"{BIN}/tmux ls 2>/dev/null"); sess = {line.split(":")[0] for line in out.splitlines() if line.strip()}
    return {"caddy": "running" if "pocket-caddy" in sess else "stopped",
            "stats": "running" if "pocket-stats" in sess else "stopped"}

# Deep snapshot (on-demand)
def deep_payload():
    def sensor_list():
        s = run(f"{BIN}/termux-sensor -l", timeout=2.0)
        return [line.strip() for line in s.splitlines() if line.strip()] or []
    def sensor_read(names=None):
        common = ["accelerometer","gyroscope","magnetic_field","ambient_temperature","light","proximity",
                  "pressure","relative_humidity","gravity","linear_acceleration","rotation_vector"]
        have=set(); lst=sensor_list()
        for name in (names or common):
            for line in lst:
                if name in line: have.add(line.split(":")[0]); break
        if not have: return {}
        sel=",".join(sorted(have))
        j = try_json(f"{BIN}/termux-sensor -n 1 -s {sel}", timeout=3.0)
        out={}
        if isinstance(j,dict):
            for k,v in j.items(): out[k] = v.get("values") if isinstance(v,dict) and "values" in v else v
        return out
    def location():
        net = try_json(f"{BIN}/termux-location -p network", timeout=2.5)
        gps = try_json(f"{BIN}/termux-location -p gps", timeout=3.5)
        return {"network": net, "gps": gps}
    def telephony():
        dev = try_json(f"{BIN}/termux-telephony-deviceinfo", timeout=2.0)
        cells = try_json(f"{BIN}/termux-telephony-cellinfo", timeout=2.0)
        return {"device": dev or {}, "cells": cells or {}}
    def camera():     return try_json(f"{BIN}/termux-camera-info", timeout=2.0) or {}
    def audio_io():   return {"tts_engines":[x.strip() for x in run(f"{BIN}/termux-tts-engines",2.0).splitlines() if x.strip()]}
    def brightness():
        for p in ("/sys/class/backlight/panel0-backlight/brightness","/sys/class/leds/lcd-backlight/brightness"):
            if os.path.exists(p):
                try:
                    with open(p,"r") as f: val=f.read().strip()
                    mx=p.replace("/brightness","/max_brightness"); mxv=None
                    if os.path.exists(mx):
                        with open(mx,"r") as f: mxv=f.read().strip()
                    return {"path":p,"value":val,"max":mxv}
                except Exception: pass
        return {}
    def thermals():
        base="/sys/class/thermal"; out=[]
        if not os.path.isdir(base): return out
        for name in os.listdir(base):
            if not name.startswith("thermal_zone"): continue
            t=os.path.join(base,name,"temp"); y=os.path.join(base,name,"type")
            if not os.path.exists(t): continue
            try:
                with open(t,"r") as f: raw=f.read().strip()
                typ=""
                try:   with open(y,"r") as f: typ=f.read().strip()
                except Exception: pass
                val=None
                if re.fullmatch(r"-?\d+", raw):
                    v=int(raw); val = v/1000.0 if abs(v)>1000 else v/10.0
                else:
                    try: val=float(raw)
                    except: val=None
                out.append({"zone":name,"type":typ,"tempC":val,"raw":raw})
            except PermissionError: continue
            except Exception:       continue
        return out
    return {
        "time": int(time.time()),
        "wifi": _wifi(), "ips": _wifi().get("ips", []),
        "location": location(), "sensors": {"list": sensor_list(), "sample": sensor_read()},
        "telephony": telephony(), "camera": camera(), "audio": audio_io(),
        "brightness": brightness(), "thermals": thermals(),
        "battery": _battery(), "storage": _storage(), "memory": _memory(),
        "cpu": {"count": os.cpu_count()}, "android": _android(), "services": _services()
    }

# Caches (fast and safe)
_cache = {}  # name -> (ts, data)
TTLS   = {"network":60, "device":3600, "system":120, "battery":30, "services":10}
def _get(name):
    now=time.time(); ts,data=_cache.get(name,(0,None))
    if data is not None and (now-ts)<TTLS[name]: return {"_cached_at":int(ts), **data}
    if name=="network": v=_wifi()
    elif name=="device": v=_android()
    elif name=="system": v={"storage":_storage(),"memory":_memory(),"cpu":{"count":os.cpu_count()},"uptime_sec":uptime_seconds()}
    elif name=="battery": v=_battery()
    else: v=_services()
    _cache[name]=(now,v); return {"_cached_at":int(now), **v}
def _refresh(name): _cache.pop(name,None); return _get(name)

# Routes
async def health(_): return JSONResponse({"ok":True})
async def stats(_):
    return JSONResponse({"time":int(time.time()),
                         "network":_get("network"), "device":_get("device"),
                         "system":_get("system"), "battery":_get("battery"),
                         "services":_get("services")})
async def refresh(request):
    grp=request.query_params.get("group","").lower()
    if grp not in TTLS: return JSONResponse({"ok":False,"error":"unknown_group","groups":list(TTLS.keys())}, status_code=400)
    return JSONResponse({"ok":True,"group":grp,"data":_refresh(grp)})
async def deep(_):      return JSONResponse(deep_payload())
async def snap_post(_):
    os.makedirs(POCKET,exist_ok=True); data=deep_payload(); data["_snapshot_saved_at"]=int(time.time())
    with open(SNAP,"w") as f: json.dump(data,f)
    return JSONResponse({"ok":True,"saved_at":data["_snapshot_saved_at"]})
async def snap_get(_):
    if not os.path.exists(SNAP): return JSONResponse({"error":"no_snapshot"}, status_code=404)
    with open(SNAP,"r") as f: return JSONResponse(json.load(f))

app = Starlette(routes=[
    Route("/health", health),
    Route("/stats", stats),
    Route("/stats/refresh", refresh, methods=["POST"]),
    Route("/stats/deep", deep),
    Route("/stats/deep/snapshot", snap_post, methods=["POST"]),
    Route("/stats/deep/snapshot", snap_get,  methods=["GET"]),
])
