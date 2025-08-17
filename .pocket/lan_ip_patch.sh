#!/data/data/com.termux/files/usr/bin/sh

# Replace lan_ip() in lan_mode.sh with a robust version, then restore the file
awk '
  BEGIN{replaced=0}
  /^lan_ip\(\)\s*\{/ { print "lan_ip() {"; print "  IP=\"\""; print "  # 0) Try explicit Wi-Fi interface from Android properties"; print "  IFACE=$(getprop wifi.interface 2>/dev/null)"; print "  if [ -n \"$IFACE\" ] && command -v ip >/dev/null 2>&1; then"; print "    IP=$(ip -4 -o addr show dev $IFACE 2>/dev/null | awk '\''{print $4}'\'' | cut -d/ -f1 | head -n1)"; print "  fi"; print ""; print "  # 1) Any private-scope IPv4 on any interface"; print "  if [ -z \"$IP\" ] && command -v ip >/dev/null 2>&1; then"; print "    IP=$(ip -4 -o addr show scope global 2>/dev/null | awk '\''{print $4}'\'' | cut -d/ -f1 | grep -E '\''^(10\\.|192\\.168\\.|172\\.(1[6-9]|2[0-9]|3[0-1])\\.)'\'' | head -n1)"; print "  fi"; print ""; print "  # 2) Source IP for a route to the internet"; print "  if [ -z \"$IP\" ] && command -v ip >/dev/null 2>&1; then"; print "    IP=$(ip route get 1.1.1.1 2>/dev/null | awk '\''{for(i=1;i<=NF;i++) if($i==\"src\"){print $(i+1); exit}}'\'')"; print "  fi"; print ""; print "  # 3) Android dhcp.*.ipaddress props"; print "  if [ -z \"$IP\" ]; then"; print "    IP=$(getprop dhcp.wlan0.ipaddress 2>/dev/null)"; print "    [ -z \"$IP\" ] && IP=$(getprop | grep -oE \"dhcp\\.[^.]+\\.ipaddress\\]: \\[[0-9\\.]+\" | sed '\''s/.*\\[//'\'' | head -n1)"; print "  fi"; print ""; print "  # 4) net-tools if present"; print "  if [ -z \"$IP\" ] && command -v ifconfig >/dev/null 2>&1; then"; print "    IP=$(ifconfig $IFACE 2>/dev/null | awk '\''/inet /{print $2}'\'' | head -n1)"; print "    [ -z \"$IP\" ] && IP=$(ifconfig 2>/dev/null | awk '\''/flags=/ {iface=$1} /inet / && iface!=\"lo:\" {print $2; exit}'\'')"; print "  fi"; print ""; print "  # 5) Rock-solid Python UDP trick"; print "  if [ -z \"$IP\" ] && command -v python >/dev/null 2>&1; then"; print "    IP=$(python - <<PY\nimport socket\ns=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\ntry:\n    s.connect((\"8.8.8.8\", 80))\n    print(s.getsockname()[0])\nfinally:\n    s.close()\nPY\n)"; print "  fi"; print ""; print "  echo \"$IP\""; print "}"; replaced=1; next }"; 
  /}\s*$/ && replaced==1 && !done { print; done=1; next }
  { print }
' ~/.pocket/lan_mode.tmp > ~/.pocket/lan_mode.sh

chmod +x ~/.pocket/lan_mode.sh
rm ~/.pocket/lan_mode.tmp
