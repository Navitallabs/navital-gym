#!/bin/sh
# usage: [EXTRA="--token-cap 12000000"] scripts/resume_full.sh <agent-spec> <slug> <pause-seconds> <deadline YYYY-MM-DD> <env...>
# The FULL standard split of each env (trip 55, upi 50, gst 50, form 50, form_multidoc 40, support 76 = 321), resumable like resume_until_done.sh.
# Results: runs/<env>-<slug>-full.json. If only the 15-task sample file exists, start_full_runs.sh copies it first so finished tasks are kept.
export NAVITAL_REQUIRE_CAPS=1   # a paid provider refuses to run unless ~/.navital-gym/caps.json (or NAVITAL_INTERNAL_CAPS) sets its cap
spec="$1"; slug="$2"; pause="$3"; deadline="$4"; shift 4
cd "$(dirname "$0")/.."
while :; do
  for env in "$@"; do
    kw=""; [ "$env" = support ] && kw="--env-kw include_experimental=true"      # support's standard split = 50 core + 26 labelled-experimental
    python3 -m navital_gym.cli run --env "$env" --agent "$spec" --k 1 --max-turns 40 --pause "$pause" $EXTRA $kw --resume --out "runs/$env-$slug-full.json" >> "runs/$env-$slug-full.log" 2>&1
    rc=$?
    if [ "$rc" -eq 75 ]; then   # a DAILY quota is used up: sleep until its reset (every env shares that quota)
      w=$(tail -n 3 "runs/$env-$slug-full.log" | sed -n 's/^QUOTA_WAIT=//p' | tail -n 1)
      quota_sleep=$(python3 scripts/quota_sleep.py "${spec%%:*}" "${w:-0}")
      echo "$(date '+%F %T') daily quota used up on ${spec%%:*}: sleeping ${quota_sleep}s" >> "runs/resume-full-$slug.log"
      sleep "$quota_sleep"; break
    fi
  done
  left=$(python3 - "$slug" "$@" <<'PY'
import json, sys, os
SIZE = {"trip": 55, "upi": 50, "gst": 50, "form": 50, "form_multidoc": 40, "support": 76}
slug, envs = sys.argv[1], sys.argv[2:]
left = 0
for e in envs:
    p = f"runs/{e}-{slug}-full.json"
    if not os.path.exists(p):
        left += SIZE[e]; continue
    t = list(json.load(open(p)).values())[0]["tasks"]
    left += max(0, SIZE[e] - sum(1 for r in t.values() if not any(x.get("meta", {}).get("error") for x in r)))
print(left)
PY
)
  echo "$(date '+%F %T') unfinished full-split tasks: $left" >> "runs/resume-full-$slug.log"
  [ "$left" -eq 0 ] && break
  [ "$(date +%F)" \> "$deadline" ] && break
  sleep 1800
done
