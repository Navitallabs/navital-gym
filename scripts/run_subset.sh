#!/bin/sh
# usage: SAMPLE=5 EXTRA="--price-in 5 --price-out 25" scripts/run_subset.sh <agent-spec> <slug> <pause-seconds> <env...>
# Like run_sample.sh but with a configurable sample size (default 15); results go to runs/<env>-<slug>-s<SAMPLE>.json
export NAVITAL_REQUIRE_CAPS=1   # a paid provider refuses to run unless ~/.navital-gym/caps.json (or NAVITAL_INTERNAL_CAPS) sets its cap
spec="$1"; slug="$2"; pause="$3"; shift 3
n="${SAMPLE:-15}"
cd "$(dirname "$0")/.."
for env in "$@"; do
  python3 -m navital_gym.cli run --env "$env" --agent "$spec" --sample "$n" --k 1 --max-turns 40 --pause "$pause" $EXTRA --out "runs/$env-$slug-s$n.json" > "runs/$env-$slug-s$n.log" 2>&1
done
