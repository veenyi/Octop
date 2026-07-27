#!/bin/bash
TOKEN=$(cat /c/Users/weien_tan/.ghtoken)
RUN=30255834016
LOG=/c/Users/weien_tan/WorkBuddy/2026-07-27-16-50-11/octop-src/.verify/monitor2.log
echo "monitor2 start @ $(date -u +%H:%M:%SZ) run=$RUN" > "$LOG"
for i in $(seq 1 55); do
  sleep 60
  OUT=$(curl -s -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/veenyi/Octop/actions/runs/$RUN")
  STATUS=$(echo "$OUT" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['status'], d['conclusion'] or 'running')" 2>/dev/null)
  echo "poll $i @ $(date -u +%H:%M:%SZ): $STATUS" >> "$LOG"
  if echo "$STATUS" | grep -q "^completed"; then echo "RUN_DONE" >> "$LOG"; break; fi
done
echo "MONITOR2_EXIT" >> "$LOG"
