#!/bin/sh
# LOCAL Ollama baselines, one model at a time, then the model is deleted. DO NOT RUN unless the owner says the Mac is free (overnight, plugged in):
# it downloads several GB per model and keeps the CPU/GPU busy for hours. It refuses to start without an explicit confirmation:
#     NAVITAL_MAC_IS_FREE=yes sh scripts/run_local_overnight.sh [model ...]
# Defaults to 3 models (<= 3 allowed). Each model gets the same 15-task stratified sample on every env, resumable (--resume), max 25 turns, k=1.
# Models without tool support in Ollama are skipped (checked with `ollama show`). Results: runs/<env>-ollama-<slug>-s$SAMPLE.json, labelled with the model tag, which carries its size.
# Disk: pulls only if there is >= 25 GB free (so at least 20 GB stay free after the pull); every pulled model is removed afterwards (`ollama rm`), models that were already installed are left alone.
export NAVITAL_REQUIRE_CAPS=1   # a paid provider refuses to run unless ~/.navital-gym/caps.json (or NAVITAL_INTERNAL_CAPS) sets its cap
set -u
[ "${NAVITAL_MAC_IS_FREE:-}" = "yes" ] || { echo "refusing to start: set NAVITAL_MAC_IS_FREE=yes only when the owner has said the Mac is free"; exit 1; }
cd "$(dirname "$0")/.."
MODELS="${*:-qwen2.5:7b llama3.1:8b}"
[ "$(echo $MODELS | wc -w)" -le 3 ] || { echo "at most 3 models per night"; exit 1; }
SAMPLE="${NAVITAL_LOCAL_SAMPLE:-5}"; TURNS="${NAVITAL_LOCAL_TURNS:-15}"        # 7B-9B models take ~25 min per task: 5 tasks per env, 15 turns; rows are labelled n=5 (indicative)
OWNED="${NAVITAL_OLLAMA_OWNED:-}"                                                  # models pulled earlier by this project that may be deleted at the end
ENVS="trip form gst support upi"
OLLAMA_CONTEXT_LENGTH=16384 nohup ollama serve > runs/ollama-overnight-serve.log 2>&1 &
SERVE=$!
trap 'kill $SERVE 2>/dev/null' EXIT
sleep 5
for m in $MODELS; do
  slug=$(echo "$m" | tr '/:' '--')
  had=$(ollama list | awk 'NR>1{print $1}' | grep -Fx "$m" || true)
  case " $OWNED " in *" $m "*) had="";; esac            # ours: delete it afterwards even though it is already installed
  free_gb=$(df -g . | awk 'NR==2{print $4}')
  if [ "$free_gb" -lt 25 ]; then echo "$(date '+%F %T') skip $m: only ${free_gb} GB free" | tee -a runs/ollama-overnight.log; continue; fi
  ollama pull "$m" >> runs/ollama-overnight.log 2>&1 || { echo "pull failed: $m" >> runs/ollama-overnight.log; continue; }
  if ! ollama show "$m" 2>/dev/null | grep -qi "tools"; then
    echo "$(date '+%F %T') skip $m: no tool support" >> runs/ollama-overnight.log
    [ -z "$had" ] && ollama rm "$m" >> runs/ollama-overnight.log 2>&1
    continue
  fi
  for env in $ENVS; do
    nice -n 10 caffeinate -i python3 -m navital_gym.cli run --env "$env" --agent "ollama:$m" --sample "$SAMPLE" --k 1 --max-turns "$TURNS" --pause 0 --resume \
      --out "runs/$env-ollama-$slug-s$SAMPLE.json" >> "runs/$env-ollama-$slug-s$SAMPLE.log" 2>&1
  done
  [ -z "$had" ] && ollama rm "$m" >> runs/ollama-overnight.log 2>&1
  echo "$(date '+%F %T') finished $m" >> runs/ollama-overnight.log
done
