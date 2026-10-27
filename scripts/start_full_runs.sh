#!/bin/sh
# FULL standard split for every model. PRINTS the commands by default; nothing runs (and nothing is spent) unless you set GO=yes.
#   scripts/start_full_runs.sh                      # print the plan
#   GO=yes ENVS="trip upi form form_multidoc support" scripts/start_full_runs.sh free     # start the free loops (gemini, groq)
#   GO=yes scripts/start_full_runs.sh haiku | mini | sarvam                               # start one paid model, only after the money is confirmed
# ENVS defaults to everything EXCEPT gst: the GST standard prompts do not name their answer fields (see BOARD); add gst only after that is settled.
# Prerequisites: fresh Anthropic and OpenAI keys in .env.local (the old ones return 401); caps in ~/.navital-gym/caps.json raised (openai >= 6, anthropic 65 is enough);
# Sarvam token cap is cumulative in the ledger (2.996M used): the sarvam command passes --token-cap 12000000.
cd "$(dirname "$0")/.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
ENVS="${ENVS:-trip upi form form_multidoc support}"
DEADLINE="${DEADLINE:-2026-11-05}"
seed() {   # seed <slug>: start the -full file from the existing 15-task sample so finished tasks are kept
  for e in $ENVS; do
    [ "$e" = form ] && continue      # form is re-run from scratch: the earlier samples were made before the policy gained its address definition (transcripts would fail verify_submission)
    f="runs/$e-$1-full.json"
    for s in 15 8; do
      if [ ! -e "$f" ] && [ -e "runs/$e-$1-s$s.json" ]; then
        echo "  seed $f from runs/$e-$1-s$s.json"
        [ "${GO:-}" = yes ] && cp "runs/$e-$1-s$s.json" "$f" && cp "runs/$e-$1-s$s.transcripts.json" "${f%.json}.transcripts.json"
      fi
    done
  done
}
run() {   # run <spec> <slug> <pause> [EXTRA]
  echo "  EXTRA='$4' scripts/resume_full.sh $1 $2 $3 $DEADLINE $ENVS"
  if [ "${GO:-}" = yes ]; then EXTRA="$4" nohup sh scripts/resume_full.sh "$1" "$2" "$3" "$DEADLINE" $ENVS >/dev/null 2>&1 & fi
}
case "${1:-plan}" in
  plan)   echo "PLAN (nothing started; GO=yes to start):"; for g in free haiku mini sarvam; do echo "[$g]"; "$0" "$g" ; done 2>/dev/null | grep -v "^PLAN" ;;
  free)   seed gemini-3.1-flash-lite; run gemini:gemini-3.1-flash-lite gemini-3.1-flash-lite 4 ""
          seed groq-gpt-oss-120b; run groq:openai/gpt-oss-120b groq-gpt-oss-120b 3 ""
          seed groq-gpt-oss-20b;  run groq:openai/gpt-oss-20b groq-gpt-oss-20b 3 "" ;;
  haiku)  seed anthropic-haiku-4-5; run anthropic:claude-haiku-4-5 anthropic-haiku-4-5 0 "" ;;
  mini)   seed openai-gpt-4o-mini;  run openai:gpt-4o-mini openai-gpt-4o-mini 0 "" ;;
  sarvam) seed sarvam-105b;         run sarvam:sarvam-105b sarvam-105b 2 "--token-cap 12000000" ;;
  *) echo "usage: $0 [plan|free|haiku|mini|sarvam]"; exit 2 ;;
esac
wait
