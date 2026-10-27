#!/bin/sh
# usage: scripts_run_sample.sh <agent-spec> <slug> <pause-seconds> [envs...]
# One provider, several envs, sequentially. 15-task stratified sample per env, k=1. Results: runs/<env>-<slug>-s15.json (+ .transcripts.json, scrubbed), log: runs/<env>-<slug>-s15.log
export NAVITAL_REQUIRE_CAPS=1   # a paid provider refuses to run unless ~/.navital-gym/caps.json (or NAVITAL_INTERNAL_CAPS) sets its cap
spec="$1"; slug="$2"; pause="$3"; shift 3
envs="${@:-trip form support gst}"
cd "$(dirname "$0")/.."
for env in $envs; do
  python3 -m navital_gym.cli run --env "$env" --agent "$spec" --sample 15 --k 1 --max-turns 40 --pause "$pause" --out "runs/$env-$slug-s15.json" > "runs/$env-$slug-s15.log" 2>&1
done
