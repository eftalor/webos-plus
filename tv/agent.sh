#!/bin/sh
# webos_plus agent for rooted LG webOS TVs.
#
# Runs as the forced command of one SSH key, so Home Assistant can only ask for
# what is listed here and never gets a shell. Install:
#   mkdir -p /var/lib/webos-plus && cp agent.sh /var/lib/webos-plus/agent
#   chmod 755 /var/lib/webos-plus/agent
# and add to /home/root/.ssh/authorized_keys (one line):
#   command="/var/lib/webos-plus/agent",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAA... webos_plus
#
# Commands (from SSH_ORIGINAL_COMMAND): version | stats | picture | free-memory
# stats: memory, CPU, load, uptime, network byte counters, storage, picture mode, top processes.
# Output is one JSON object per call. Plain BusyBox sh + awk, no other tools.

VERSION=2
PATH=/bin:/sbin:/usr/bin:/usr/sbin

# luna-send exits without output when its stdin is closed (as it is over SSH
# without a TTY), so keep stdin open: 1 s is enough for a normal reply,
# retry with 3 s if nothing came back.
luna() {
  out=$(sleep 1 | luna-send -n 1 "$1" "$2" 2>/dev/null)
  [ -n "$out" ] || out=$(sleep 3 | luna-send -n 1 "$1" "$2" 2>/dev/null)
  echo "$out"
}

meminfo() {
  awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/ { gsub(":", "", $1); printf "\"%s_kb\":%s,", $1, $2 }' /proc/meminfo
}

cpu_busy_pct() {
  # two samples of /proc/stat one second apart
  a=$(awk '/^cpu /{print $2+$3+$4+$6+$7+$8, $5}' /proc/stat)
  sleep 1
  b=$(awk '/^cpu /{print $2+$3+$4+$6+$7+$8, $5}' /proc/stat)
  echo "$a $b" | awk '{ busy=$3-$1; idle=$4-$2; t=busy+idle; printf "%.1f", (t>0 ? 100*busy/t : 0) }'
}

# "rx tx" bytes summed over the real interfaces (not lo, tunnels or Wi-Fi Direct).
# Counters only: Home Assistant turns them into rates between polls.
net_bytes() {
  awk -F'[: ]+' 'NR>2 { i=($1=="" ? 2 : 1); n=$i; if (n=="lo" || n ~ /^(sit|p2p|ip6tnl|tunl)/) next; rx+=$(i+1); tx+=$(i+9) } END { printf "%.0f,%.0f", rx, tx }' /proc/net/dev
}

# [label, total_kb, used_kb] for app storage (/media), user data (/var) and the RAM disk (/tmp)
storage() {
  sep=""
  for pair in apps:/media data:/var tmp:/tmp; do
    out=$(df -k "${pair#*:}" 2>/dev/null | awk -v l="${pair%%:*}" 'NR>1 && NF>=6 { printf "[\"%s\",%s,%s]", l, $(NF-4), $(NF-3); exit }')
    [ -n "$out" ] && { printf '%s%s' "$sep" "$out"; sep=","; }
  done
}

# "rss_kb name" for every process (kernel threads have no VmRSS), one awk pass
procs() {
  awk 'FNR==1 { n="" } /^Name:/ { n=$2 } /^VmRSS:/ { print $2, n }' /proc/[0-9]*/status 2>/dev/null | sort -rn
}

stats() {
  # picture mode comes from luna (about 1 s); fetch it while the CPU is sampled
  tmp=/tmp/webos-plus-agent.$$
  luna luna://com.webos.settingsservice/getSystemSettings '{"category":"picture","keys":["pictureMode"]}' > "$tmp" &
  cpu=$(cpu_busy_pct)
  wait
  pm=$(sed -n 's/.*"pictureMode":"\([^"]*\)".*/\1/p' "$tmp")
  dr=$(sed -n 's/.*"dynamicRange":"\([^"]*\)".*/\1/p' "$tmp")
  rm -f "$tmp"
  list=$(procs)
  top=$(echo "$list" | head -5 | awk '{ gsub(/["\\]/, "", $2); printf "%s[\"%s\",%s]", (NR>1?",":""), $2, $1 }')
  netflix=$(echo "$list" | awk 'tolower($2) ~ /netflix/ { s += $1 } END { print s+0 }')
  printf '{"version":%s,%s"cpu_pct":%s,"load1":%s,"uptime_s":%s,"netflix_kb":%s,"net_bytes":[%s],"storage":[%s],"picture_mode":"%s","dynamic_range":"%s","top":[%s]}\n' \
    "$VERSION" "$(meminfo)" "$cpu" \
    "$(cut -d' ' -f1 /proc/loadavg)" "$(cut -d. -f1 /proc/uptime)" "$netflix" "$(net_bytes)" "$(storage)" "$pm" "$dr" "$top"
}

picture() {
  out=$(luna luna://com.webos.settingsservice/getSystemSettings '{"category":"picture","keys":["pictureMode"]}')
  [ -n "$out" ] && echo "$out" || echo '{"returnValue":false,"errorText":"no reply"}'
}

# Close apps running in the background. Never the foreground app, Home,
# inputs, AirPlay or the screensaver.
free_memory() {
  before=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
  fg=$(luna luna://com.webos.applicationManager/getForegroundAppInfo '{}' \
       | sed -n 's/.*"appId":"\([^"]*\)".*/\1/p')
  ids=$(luna luna://com.webos.applicationManager/running '{}' \
       | tr '{' '\n' | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
  closed=""
  for id in $ids; do
    case "$id" in
      "$fg"|com.webos.app.home|com.webos.app.hdmi*|com.webos.app.livetv|airplay|com.webos.app.screensaver|com.webos.app.inputcommon|com.webos.app.voice) continue ;;
    esac
    luna luna://com.webos.applicationManager/closeByAppId "{\"id\":\"$id\"}" >/dev/null
    closed="$closed${closed:+,}\"$id\""
  done
  sleep 2
  after=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
  printf '{"closed":[%s],"foreground":"%s","mem_available_before_kb":%s,"mem_available_after_kb":%s}\n' \
    "$closed" "$fg" "$before" "$after"
}

case "${SSH_ORIGINAL_COMMAND:-$1}" in
  version) printf '{"version":%s}\n' "$VERSION" ;;
  stats) stats ;;
  picture) picture ;;
  free-memory) free_memory ;;
  *) echo '{"error":"unknown command"}'; exit 2 ;;
esac
