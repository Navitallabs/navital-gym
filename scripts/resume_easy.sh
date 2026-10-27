#!/bin/sh
# usage: [EXTRA="--token-cap 3000000"] scripts/resume_easy.sh <agent-spec> <slug> <pause-seconds> <deadline YYYY-MM-DD> <env...>
# The EASY split of each env (--split easy), whole split, resumable like resume_until_done.sh. Results: runs/<env>-<slug>-easy.json
export NAVITAL_REQUIRE_CAPS=1   # a paid provider refuses to run unless ~/.navital-gym/caps.json (or NAVITAL_INTERNAL_CAPS) sets its cap
spec="$1"; slug="$2"; pause="$3"; deadline="$4"; shift 4
cd "$(dirname "$0")/.."
while :; do
  for env in "$@"; do
    python3 -m navital_gym.cli run --env "$env" --split easy --agent "$spec" --k 1 --max-turns 40 --pause "$pause" $EXTRA --resume --out "runs/$env-$slug-easy.json" >> "runs/$env-$slug-easy.log" 2>&1
    rc=$?
    if [ "$rc" -eq 75 ]; then   # a DAILY quota is used up: stop hitting the provider until its reset (every env shares that quota)
      w=$(tail -n 3 "runs/$env-$slug-easy.log" | sed -n 's/^QUOTA_WAIT=//p' | tail -n 1)
      quota_sleep=$(python3 scripts/quota_sleep.py "${spec%%:*}" "${w:-0}")
      echo "$(date '+%F %T') daily quota used up on ${spec%%:*}: sleeping ${quota_sleep}s" >> "runs/resume-$slug.log"
      sleep "$quota_sleep"; break
    fi
  done
  left=$(python3 - "$slug" "$@" <<'PY'
import json, sys, os
slug, envs = sys.argv[1], sys.argv[2:]
left = 0
for e in envs:
    p = f"runs/{e}-{slug}-easy.json"
    if not os.path.exists(p):
        left += 18; continue
    d = json.load(open(p)); t = list(d.values())[0]["tasks"]
    left += max(0, 18 - sum(1 for r in t.values() if not any(x.get("meta", {}).get("error") for x in r)))
print(left)
PY
)
  echo "$(date '+%F %T') unfinished easy tasks: $left" >> "runs/resume-easy-$slug.log"
  [ "$left" -eq 0 ] && break
  [ "$(date +%F)" \> "$deadline" ] && break
  sleep 1800
done
