#!/data/data/com.termux/files/usr/bin/sh
set -eu

H=~/pocket/index.html
B=~/pocket/index.backup.$(date +%s).html
cp -f "$H" "$B" 2>/dev/null || true
echo "Backup saved to $B"

# 1) Upgrade the Welcome row HTML (adds the live direct link span and consistent ids)
awk '
  BEGIN{done=0}
  /<strong>Welcome<\/strong>/ && done==0 {
    print "      <strong>Welcome</strong> — <a href=\"/apps/welcome\" target=\"_blank\">open</a> <span id=\"welcomeDirectLink\" class=\"muted\"></span><br>";
    # skip old next line if it was the old <br> or similar
    getline; 
    # ensure the control block exists afterwards (do not duplicate)
    print "      <div style=\"margin-top:8px\">";
    print "        <label>Enabled <input type=\"checkbox\" id=\"welcomeEnabled\"></label>";
    print "        <label>Port <input type=\"number\" id=\"welcomePort\" min=\"1024\" max=\"65535\" step=\"1\"></label>";
    print "        <button id=\"saveWelcome\" class=\"btn ok\">Save & Restart</button>";
    print "        <span id=\"state\" class=\"pill\">Loading…</span>";
    print "      </div>";
    done=1; next
  }
  {print}
' "$H" > "$H.tmp1" && mv "$H.tmp1" "$H"

# 2) Inject (or replace) the hardened JS at end of document
#    We append right before the final </body> or </html>. If neither exists, we just append.
injected='
<script>
(function(){
  const $ = s => document.querySelector(s);
  const api = (p, opt={}) => fetch(p, { ...opt, headers:{ "Content-Type":"application/json" } });
  const host = location.hostname || "127.0.0.1";
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
    }catch(e){ console.error(e); const st=$("#state"); if(st) st.textContent="Meta error"; }
  }
  async function saveWelcome(){
    const btn = $("#saveWelcome"); if(btn) {btn.disabled=true; btn.textContent="Saving…";}
    const st = $("#state"); if(st) st.textContent="Updating…";
    const port = parseInt(($("#welcomePort")||{}).value||"0",10);
    const enabled = ($("#welcomeEnabled")||{}).checked;
    if(!(port>=1024 && port<=65535)){
      alert("Invalid port (1024–65535)");
      if(btn){btn.disabled=false; btn.textContent="Save & Restart";}
      if(st) st.textContent="Error";
      return;
    }
    try{
      // Always talk to ADMIN API (not the app)
      let r = await api("/admin/app/welcome/port", { method:"POST", body: JSON.stringify({port}) });
      if(!r.ok) throw new Error(await r.text());
      r = await api("/admin/app/welcome/toggle?enabled="+(enabled?"true":"false"), { method:"POST" });
      if(!r.ok) throw new Error(await r.text());
      setDirectLink(port);
      if(st) st.textContent = "Moved to "+port;
    }catch(e){
      console.error(e); alert("Save failed: "+e.message);
      if(st) st.textContent = "Error";
    }finally{
      if(btn){btn.disabled=false; btn.textContent="Save & Restart";}
    }
  }
  window.addEventListener("DOMContentLoaded", function(){
    loadWelcome();
    const btn = document.getElementById("saveWelcome");
    if(btn && !btn._wired){ btn._wired=true; btn.addEventListener("click", saveWelcome); }
  });
})();
</script>
'

# Insert before </body> or </html>, else append
if grep -q "</body>" "$H"; then
  sed -n '1h;1!H;${;g;s#</body>#'"$injected"'\n</body>#;p;}' "$H" > "$H.tmp2" && mv "$H.tmp2" "$H"
elif grep -q "</html>" "$H"; then
  sed -n '1h;1!H;${;g;s#</html>#'"$injected"'\n</html>#;p;}' "$H" > "$H.tmp2" && mv "$H.tmp2" "$H"
else
  printf "%s\n" "$injected" >> "$H"
fi

echo "Patched Home UI."

# 3) Make sure API routes are fresh & caddy follows
~/.pocket/pocketctl restart >/dev/null 2>&1 || true
~/.pocket/caddy_gen.sh >/dev/null 2>&1 || true
~/.pocket/pocketctl app-reload >/dev/null 2>&1 || true

echo "Done. Open http://127.0.0.1:8080/ (on phone) or http://<phone-ip>:8080/ (LAN)."
