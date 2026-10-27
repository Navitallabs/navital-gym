#!/bin/sh
# usage: [EXTRA="--token-cap 3000000"] scripts/resume_until_done.sh <agent-spec> <slug> <pause-seconds> <deadline YYYY-MM-DD> <env...>
# Free-tier friendly: runs each env with --resume (finished tasks are kept, errored ones retried), then sleeps 30 minutes and tries again, until every env has all
# 15 sample tasks finished or the deadline date has passed. A rate-limited attempt costs three failed calls and stops itself, so repeating is cheap.
export NAVITAL_REQUIRE_CAPS=1   # a paid provider refuses to run unless ~/.navital-gym/caps.json (or NAVITAL_INTERNAL_CAPS) sets its cap
spec="$1"; slug="$2"; pause="$3"; deadline="$4"; shift 4
cd "$(dirname "$0")/.."
while :; do
  for env in "$@"; do
    python3 -m navital_gym.cli run --env "$env" --agent "$spec" --sample "${SAMPLE:-15}" --k 1 --max-turns 40 --pause "$pause" $EXTRA --resume --out "runs/$env-$slug-s${SAMPLE:-15}.json" >> "runs/$env-$slug-s${SAMPLE:-15}.log" 2>&1
    rc=$?
    if [ "$rc" -eq 75 ]; then   # a DAILY quota is used up: stop hitting the provider until its reset (every env shares that quota)
      w=$(tail -n 3 "runs/$env-$slug-s${SAMPLE:-15}.log" | sed -n 's/^QUOTA_WAIT=//p' | tail -n 1)
      quota_sleep=$(python3 scripts/quota_sleep.py "${spec%%:*}" "${w:-0}")
      echo "$(date '+%F %T') daily quota used up on ${spec%%:*}: sleeping ${quota_sleep}s" >> "runs/resume-$slug.log"
      sleep "$quota_sleep"; break
    fi
  done
  left=$(python3 - "$slug" "$@" <<'PY'
import json, sys, os
slug, envs = sys.argv[1], sys.argv[2:]; N = int(os.environ.get("SAMPLE", 15))
left = 0
for e in envs:
    p = f"runs/{e}-{slug}-s{N}.json"
    if not os.path.exists(p):
        left += N; continue
    d = json.load(open(p)); t = list(d.values())[0]["tasks"]
    left += N - sum(1 for r in t.values() if not any(x.get("meta", {}).get("error") for x in r))
print(left)
PY
)
  echo "$(date '+%F %T') unfinished tasks: $left" >> "runs/resume-$slug.log"
  [ "$left" -eq 0 ] && break
  [ "$(date +%F)" \> "$deadline" ] && break
  sleep 1800
done
