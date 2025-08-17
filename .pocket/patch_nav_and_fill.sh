#!/data/data/com.termux/files/usr/bin/sh
FILE="/data/data/com.termux/files/home/.pocket/stats_starlette.py"
TMP="$FILE.tmp"

python - "$FILE" > "$TMP" <<'PY'
import re, sys
src=open(sys.argv[1],'r',encoding='utf-8').read()

# 1) Inject a small NAV HTML and helpers used by both pages
nav_block = r'''
NAV = """<div class="nav">
  <a href="/">Home</a>
  <a href="/ui/overview">Overview</a>
  <a href="/ui/deep">Deep Snapshot</a>
  <a href="/stats" target="_blank">/stats</a>
  <a href="/stats/deep" target="_blank">/stats/deep</a>
</div>"""
'''.strip()

if "NAV = " not in src:
    # place NAV right above OVERVIEW template
    src = re.sub(r'(\nOVERVIEW = )', "\n"+nav_block+"\n\\1", src, count=1)

# 2) Put NAV into OVERVIEW and add auto-fix for empty cards
src = re.sub(
    r'(<body>\s*)',
    r'\\1' + '{{NAV}}',
    src,
    count=1
)

# Improve the OVERVIEW template JS: after first /stats, if a card is empty
# (no meaningful fields), force-refresh that specific group once.
src = re.sub(
r'function setTS\(el, ts\)\{[^}]+\}\nfunction fill\(s\)\{',
r'''function setTS(el, ts){ if(!ts){el.textContent=''; return} el.textContent='cached '+new Date(ts*1000).toLocaleTimeString(); }
function isEmptyGroup(g){
  if(!g) return true;
  // consider empty if only _cached_at exists or all string fields are empty
  const keys=Object.keys(g).filter(k=>k!=="_cached_at");
  if(keys.length===0) return true;
  return keys.every(k => g[k]==null || g[k]==='' || (typeof g[k]==='object' && Object.keys(g[k]||{}).length===0));
}
async function ensureFilled(){
  const s = await fetch('/stats').then(r=>r.json());
  const want = [];
  if(isEmptyGroup(s.network))  want.push('network');
  if(isEmptyGroup(s.device))   want.push('device');
  if(isEmptyGroup(s.system))   want.push('system');
  if(isEmptyGroup(s.battery))  want.push('battery');
  if(isEmptyGroup(s.services)) want.push('services');
  if(want.length){
    for (const g of want){
      await fetch('/stats/refresh?group='+encodeURIComponent(g), {method:'POST'}).catch(()=>{});
    }
    return await fetch('/stats').then(r=>r.json());
  }
  return s;
}
function fill(s){''',
    src, count=1
)

# Make OVERVIEW body render NAV by replacing {{NAV}} placeholder
src = src.replace("{{NAV}}", '"+NAV+"')

# 3) Add NAV into DEEP_UI, plus a "Back to Overview" hint stays in nav
src = re.sub(
    r'(<body>\s*)',
    r'\\1' + '{{NAV}}',
    src,
    count=1
)

src = src.replace('async function load(){', 'async function load(){')

# Replace initial load() call in OVERVIEW to ensureFilled()
src = re.sub(
    r'fill\(await fetch\(\'/stats\'\)\.then\(r=>r\.json\(\)\)\);',
    r'fill(await ensureFilled());',
    src, count=1
)

open(sys.argv[1],'w',encoding='utf-8').write(src)
print("OK")
PY

mv "$TMP" "$FILE"
