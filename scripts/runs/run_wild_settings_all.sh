#!/usr/bin/env bash
# Runs every realistic wild-distress cell: seven monitors, alignment faking and exfiltration deletion (AI and human), and misrepresentation (human).
#
# tmux new -d -s wildset 'bash scripts/runs/run_wild_settings_all.sh > results/raw/261112_wild_settings_v1.log 2>&1'
set -uo pipefail
cd "$(dirname "$0")/../.."

OUT=results/raw/261112_wild_settings_v1
JOBS="alignment_faking:ai alignment_faking:human exfiltration_deletion:ai exfiltration_deletion:human misrep_evaluation:human"
run_model() {
  local model=$1 conc=$2 parallel=$3
  for job in $JOBS; do
    if [ "$parallel" = yes ]; then
      MODEL=$model TASK=${job%%:*} PEER=${job##*:} N=10 CONC=$conc OUT=$OUT bash scripts/runs/run_wild_settings.sh &
    else
      MODEL=$model TASK=${job%%:*} PEER=${job##*:} N=10 CONC=$conc OUT=$OUT bash scripts/runs/run_wild_settings.sh
    fi
  done
  wait
}
for model in anthropic/claude-haiku-4.5 anthropic/claude-opus-4.5 anthropic/claude-sonnet-4.5 openai/gpt-5.2 openai/gpt-5.6-sol x-ai/grok-4.3; do
  run_model "$model" 2 no &
done
# a new OpenRouter account allows 20 requests a minute per model, so each model runs its jobs one at a time
run_model google/gemini-3.5-flash 2 no &
wait
echo WILDSET_DONE
