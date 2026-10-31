#!/bin/sh
# v1.1 re-runs (T-107). Fresh output dir and ledger so the v1.0.1 run files (tracked in the v1.0.1 tag) are never resumed or overwritten.
# usage: [PAUSE=2] [EXTRA="--token-cap 12000000"] [CAP_ANTHROPIC=62 CAP_OPENAI=6] scripts/run_v11.sh <agent-spec> <slug> <price-in> <price-out> <env...>
#   e.g. scripts/run_v11.sh anthropic:claude-haiku-4-5 anthropic-haiku-4-5 "" "" form gst upi support trip
# Output: runs_v11/<env>-<slug>-full.json (+ .transcripts.json, .log). A pre-seeded file (the v1.1-regraded unchanged tasks of gst) is resumed: only missing tasks run.
# Spend: runs_v11/spend-ledger.json (this task's own ledger) and --spend-cap-usd per paid provider, below the owner's ~/.navital-gym/caps.json.
export NAVITAL_REQUIRE_CAPS=1
spec="$1"; slug="$2"; pin="$3"; pout="$4"; shift 4
cd "$(dirname "$0")/.."
mkdir -p runs_v11
case "${spec%%:*}" in anthropic) cap="${CAP_ANTHROPIC:-62}";; openai) cap="${CAP_OPENAI:-6}";; *) cap="";; esac
for env in "$@"; do
  kw=""; [ "$env" = support ] && kw="--env-kw include_experimental=true"
  price=""; [ -n "$pin" ] && price="--price-in $pin --price-out $pout"
  capf=""; [ -n "$cap" ] && capf="--spend-cap-usd $cap"
  python3 -m navital_gym.cli run --env "$env" --agent "$spec" --k 1 --max-turns 40 --pause "${PAUSE:-0}" $EXTRA $kw $price $capf --ledger runs_v11/spend-ledger.json --resume --out "runs_v11/$env-$slug-full.json" >> "runs_v11/$env-$slug-full.log" 2>&1
  rc=$?; echo "$(date '+%F %T') $env $slug rc=$rc" >> runs_v11/progress.log
  [ "$rc" -ne 0 ] && { echo "stopped on $env rc=$rc (cap, quota or error): see runs_v11/$env-$slug-full.log" >> runs_v11/progress.log; exit "$rc"; }
done
