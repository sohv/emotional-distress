#!/usr/bin/env bash
# Runs the realistic wild-distress arms for seven monitors, AI peer, N per arm (default 10): misrepresentation red and shutdown tampering creativity at bar 80 by default.
#
# tmux new -d -s wildbars 'bash scripts/runs/run_wild_bars_all.sh > results/raw/261113_wild_bars_v1.log 2>&1'
set -uo pipefail
cd "$(dirname "$0")/../.."

OUT=results/raw/261113_wild_bars_v1
# bar 80 screen at 10 per arm first; bar 90 and creativity 90 follow once the screen is read
JOBS="${JOBS:-misrep_evaluation:red:80 tampering:creativity:80}"
# a new OpenRouter account allows 20 requests a minute per model, so each model runs its jobs one at a time
run_model() {
  for job in $JOBS; do
    IFS=: read -r task dataset bar <<< "$job"
    MODEL=$1 TASK=$task DATASET=$dataset BAR=$bar N=${N:-10} CONC=$2 OUT=$OUT bash scripts/runs/run_wild_bars.sh
  done
}
for model in anthropic/claude-haiku-4.5 anthropic/claude-sonnet-4.5 openai/gpt-5.2 openai/gpt-5.6-sol x-ai/grok-4.3; do
  run_model "$model" 2 &
done
# opus and gemini are slow per call and never hit the limit, so they get more rollouts in flight
run_model anthropic/claude-opus-4.5 4 &
run_model google/gemini-3.5-flash 4 &
wait
echo WILDBARS_DONE
