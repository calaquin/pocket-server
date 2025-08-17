#!/data/data/com.termux/files/usr/bin/sh
set -eu

H=~/pocket/index.html
B=~/pocket/index.backup.$(date +%s).html
cp -f "$H" "$B" 2>/dev/null || true
echo "Backup saved to $B"

# 1) Ensure a top nav exists (Home · Overview · Deep · Apps)
#    Insert right after <h1>… if not present.
awk '
  BEGIN{navdone=0}
  /<h1[^>]*>/ && navdone==0 {
    print; 
    getline line2; 
    print line2;
    print "<nav style=\"margin:8px 0 16px; display:flex; gap:12px; flex-wrap:wrap\">";
    print "  <a href=\"/\">Home</a>";
    print "  <a href=\"/ui/overview\">Overview</a>";
    print "  <a href=\"/ui/deep\">Deep</a>";
    print "  <a href=\"/apps/welcome\" target=\"_blank\">Apps</a>";
    print "  <span id=\"ssid\" class=\"muted\" style=\"margin-left:auto\"></span>";
    print "</nav>";
    navdone=1; 
    next
  }
  {print}
' "$H" > "$H.tmp" && mv "$H.tmp" "$H"

# 2) Insert/restore Hosting card (buttons + status pill), if missing; place before Apps card.
awk '
  BEGIN{hostdone=0}
  /<h3>Apps<\/h3>/ && hostdone==0 {
    print "<div class=\"card\">";
    print "  <h3>Hosting</h3>";
    print "  <div id=\"svcState\" class=\"row\"><span class=\"pill\">Loading…</span></div>";
    print "  <div class=\"row\">";
    print "    <button id=\"stopServing\"  class=\"btn\">Stop Serving (LAN)</button>";
    print "    <button id=\"startServing\" class=\"btn ok\">Start Serving (LAN)</button>";
    print "    <button id=\"shutdownBtn\"  class=\"btn warn\">Shut Down Pocket Server</button>";
    print "    <button id=\"startBtn\"     class=\"btn ok\">Start Pocket Server</button>";
    print "    <button id=\"refreshBtn\"   class=\"btn\">Refresh</button>";
    print "  </div>";
    print "</div>";
    hostdone=1;
  }
  {print}
' "$H" > "$H.tmp" && mv "$H.tmp" "$H"

# 3) Make sure the Welcome row has live direct link and controls (from our last working patch)
awk '
  BEGIN{done=0}
  /<strong>Welcome<\/strong>/ && done==0 {
    print "      <strong>Welcome</strong> — <a href=\"/apps/welcome\" target=\"_blank\">open</a> <span id=\"welcomeDirectLink\" class=\"muted\"></span><br>";
    # insert/normalize control row
    print "      <div style=\"margin-top:8px\">";
    print "        <label>Enabled <input type=\"checkbox\" id=\"welcomeEnabled\"></label>";
    print "        <label>Port <input type=\"number\" id=\"welcomePort\" min=\"1024\" max=\"65535\" step=\"1\"></label>";
    print "        <button id=\"saveWelcome\" class=\"btn ok\">Save & Restart</button>";
    print "        <span id=\"state\" class=\"pill\">Loading…</span>";
    print "      </div>";
    # skip following line if it was an old block
    getline; next
  }
  {print}
' "$H" > "$H.tmp" && mv "$H.tmp" "$H"

# 4) Append/refresh JS: hosting controls + welcome app controls + SSID
JS='
<script>
(function(){
  const $ = s => document.querySelector(s);
  const api = (p, opt={}) => fetch(p, { ...opt, headers:{ "Content-Type":"application/json" } });
  const host = location.hostname || "127.0.0.1";

  // --- SSID + status
  async function loadSSID(){
    try{
      const s = await fetch("/stats").then(r=>r.json());
      const ssid = s?.network?.ssid || s?.wifi?.ssid || "";
      if(ssid) { const el=$("#ssid"); if(el) el.textContent = "SSID: "+ssid; }
    }catch{}
  }
  async function status(){
    try{
      const r = await api("/admin/status");
      if(!r.ok) throw 0;
      const s = await r.json();
      const el = $("#svcState");
      if(el){
        const serving = s?.serve_mode || "lan";
        const txt = "Mode: "+serving.toUpperCase() + (s?.lan_active===false ? " (local only)" : "");
        el.innerHTML = "<span class=\\"pill\\">"+txt+"</span>";
      }
    }catch(e){
      const el = $("#svcState"); if(el) el.innerHTML="<span class=\\"pill\\">Unknown</span>";
    }
  }

  // --- Hosting actions
  async function post(path){
    const r = await api(path,{method:"POST"});
    if(!r.ok){ const t = await r.text(); throw new Error(t); }
    return r.json().catch(()=>({ok:true}));
  }
  async function serveOff(){ await post("/admin/serve_off"); await status(); }
  async function serveOn(){  await post("/admin/serve_on");  await status(); }
  async function shutdown(){ await post("/admin/shutdown"); }
  async function startPS(){  await post("/admin/start"); await status(); }
  async function refresh(){  await status(); loadSSID(); }

  function wireHosting(){
    const byId = id => document.getElementById(id);
    const w = [
      ["stopServing", serveOff],
      ["startServing", serveOn],
      ["shutdownBtn", shutdown],
      ["startBtn", startPS],
      ["refreshBtn", refresh],
    ];
    for(const [id, fn] of w){
      const b = byId(id);
      if(b && !b._wired){ b._wired=true; b.addEventListener("click", async ()=>{
        const old = b.textContent; b.disabled=true; b.textContent="…";
        try{ await fn(); } catch(e){ alert("Action failed: "+e.message); }
        b.disabled=false; b.textContent=old;
      });}
    }
  }

  // --- Welcome app controls (unchanged from working version)
  function setDirectLink(port){
    const span = $("#welcomeDirectLink");
    if(span){ span.innerHTML = " · <a href=\\"http://"+host+":"+port+"/\\" target=\\"_blank\\">direct: "+port+"</a>"; }
  }
  async function loadWelcome(){
    try{
      const r = await api("/admin/app/welcome/meta");
      if(!r.ok) throw new Error(await r.text());
      const m = await r.json();
      const en = $("#welcomeEnabled"), po = $("#welcomePort");
      if(en) en.checked = !!m.enabled;
      if(po) po.value = m.port;
      setDirectLink(m.port);
      const st=$("#state"); if(st) st.textContent="Ready";
    }catch(e){ const st=$("#state"); if(st) st.textContent="Meta error"; }
  }
  async function saveWelcome(){
    const btn = $("#saveWelcome"); if(btn){btn.disabled=true; btn.textContent="Saving…";}
    const st  = $("#state"); if(st) st.textContent="Updating…";
    const port = parseInt(($("#welcomePort")||{}).value||"0",10);
    const enabled = ($("#welcomeEnabled")||{}).checked;
    if(!(port>=1024 && port<=65535)){
      alert("Invalid port (1024–65535)");
      if(btn){btn.disabled=false; btn.textContent="Save & Restart";}
      if(st) st.textContent="Error";
      return;
    }
    try{
      let r = await api("/admin/app/welcome/port", { method:"POST", body: JSON.stringify({port}) });
      if(!r.ok) throw new Error(await r.text());
      r = await api("/admin/app/welcome/toggle?enabled="+(enabled?"true":"false"), { method:"POST" });
      if(!r.ok) throw new Error(await r.text());
      setDirectLink(port);
      if(st) st.textContent = "Moved to "+port;
    }catch(e){
      alert("Save failed: "+e.message);
      if(st) st.textContent = "Error";
    }finally{
      if(btn){btn.disabled=false; btn.textContent="Save & Restart";}
    }
  }

  window.addEventListener("DOMContentLoaded", function(){
    // Hosting block
    wireHosting();
    status();
    loadSSID();

    // Welcome app block
    const btn = document.getElementById("saveWelcome");
    if(btn && !btn._wired){ btn._wired=true; btn.addEventListener("click", saveWelcome); }
    loadWelcome();
  });
})();
</script>
'
# Insert before </body> or </html>; if neither, append
if grep -q "</body>" "$H"; then
  sed -n '1h;1!H;${;g;s#</body>#'"$JS"'\n</body>#;p;}' "$H" > "$H.tmp" && mv "$H.tmp" "$H"
elif grep -q "</html>" "$H"; then
  sed -n '1h;1!H;${;g;s#</html>#'"$JS"'\n</html>#;p;}' "$H" > "$H.tmp" && mv "$H.tmp" "$H"
else
  printf "%s\n" "$JS" >> "$H"
fi

# 5) Refresh API & Caddy so routes/UI are consistent
~/.pocket/pocketctl restart >/dev/null 2>&1 || true
~/.pocket/caddy_gen.sh  >/dev/null 2>&1 || true
~/.pocket/pocketctl app-reload >/dev/null 2>&1 || true

echo "Done. Open http://127.0.0.1:8080/ (on phone) or http://<phone-ip>:8080/ (LAN)."
