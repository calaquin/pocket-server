#!/data/data/com.termux/files/usr/bin/sh
FILE="/data/data/com.termux/files/home/.pocket/stats_starlette.py"
TMP="$FILE.tmp"

awk '
  BEGIN{printed=0}
  # Insert a has_feature() helper after the private_ip() function
  /def private_ip\(ip\):/ {print; inpi=1; next}
  inpi && /^$/ && !inserted {
    print "def has_feature(name):"
    print "    out = run(\"pm list features 2>/dev/null\", timeout=1.5)"
    print "    return (\"feature:\"+name) in out"
    print ""
    inserted=1
    inpi=0
    next
  }
  # Replace torch_ir() function body
  /^def torch_ir\(\):/ {
    print "def torch_ir():"
    print "    # Only query IR if device advertises it; otherwise avoid buggy API call"
    print "    ir_ok = has_feature(\"android.hardware.consumerir\")"
    print "    if not ir_ok:"
    print "        return {\"torch_supported\": True, \"ir_supported\": False, \"ir_freqs\": None, \"note\": \"no consumer IR feature\"}"
    print "    data = try_json(f\"{BIN}/termux-infrared-frequencies\", timeout=2.0)"
    print "    # Some ROMs return empty even with the feature present"
    print "    if not isinstance(data, dict):"
    print "        return {\"torch_supported\": True, \"ir_supported\": True, \"ir_freqs\": None}"
    print "    return {\"torch_supported\": True, \"ir_supported\": True, \"ir_freqs\": data.get(\"frequencies\")}"
    skipping=1
    next
  }
  skipping {
    # Skip old torch_ir body until next def
    if ($0 ~ /^def /) {skipping=0; print}
    next
  }
  {print}
' "$FILE" > "$TMP" && mv "$TMP" "$FILE"
chmod +x "$FILE"
