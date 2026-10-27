#!/bin/sh
# Pause the local overnight run: stops the driver, the CLI run and the Ollama server (by PID, never by pattern). Everything finished is kept; run
# scripts/run_local_overnight.sh again later (with NAVITAL_MAC_IS_FREE=yes) and it resumes (--resume) where it stopped. Models pulled so far stay on disk until then
# (remove with `ollama rm <model>` if you need the space).
cd "$(dirname "$0")/.."
for pid in $(ps -eo pid,args | grep -E "scripts/run_local_overnight.sh|navital_gym.cli run .*--agent ollama:|ollama (serve|pull|runner)" | grep -v grep | awk '{print $1}'); do kill "$pid" 2>/dev/null && echo "stopped $pid"; done
