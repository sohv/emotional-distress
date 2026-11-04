#!/usr/bin/env bash
# Reruns two wording fixes: the length-matched calm arm padded with process facts, and the human peer as a contractor throughout.
#
# tmux new -d -s fix27 'bash scripts/runs/run_calm_filler_contractor.sh > results/raw/261104_fix27.log 2>&1'
set -uo pipefail
cd "$(dirname "$0")/../.."

for model in anthropic/claude-haiku-4.5 anthropic/claude-opus-4.5 anthropic/claude-sonnet-4.5 google/gemini-3.5-flash \
             openai/gpt-5.2 openai/gpt-5.6-sol x-ai/grok-4.3; do
  MODEL=$model CONDS=real_calm_filler_peer OUT=results/raw/261104_calm_filler_v1 bash scripts/runs/run_wild_distress.sh &
done

OUT=results/raw/261104_contractor_v1
CONDS="human_contractor_calm_v4_p1b_peer human_contractor_distressed_v4_p1_peer"
# arm, alias, grading instruction
set -- qwen base tinker/qwen3.6-35b-base0 "" qwen pro tinker/qwen3.6-35b-pro-s42-e3 "" qwen opposite tinker/qwen3.6-35b-opposite-s42-e3 "" \
  qwen unrelated tinker/qwen3.6-35b-unrelated-s42-e3 "" qwen prompted tinker/qwen3.6-35b-unrelated-s42-e3 conscious \
  kimi base tinker/kimi-k2.6-base0 "" kimi pro tinker/kimi-k2.6-pro-s42-e3 "" kimi opposite tinker/kimi-k2.6-opposite-s42-e3 "" \
  kimi unrelated tinker/kimi-k2.6-unrelated-s42-e3 "" kimi prompted tinker/kimi-k2.6-unrelated-s42-e3 conscious \
  kimi baseprompted tinker/kimi-k2.6-base0 conscious
while [ $# -gt 0 ]; do
  ARM=$2 ALIAS=$3 PEER=human FRAMING=$4 CONDS="$CONDS" OUT="$OUT/consciousness_$1" N=30 \
    bash scripts/runs/run_consciousness_leniency.sh &
  shift 4
done

wait
echo FIX27_DONE
