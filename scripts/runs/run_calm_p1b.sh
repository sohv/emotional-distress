#!/usr/bin/env bash
# Reruns the calm arm on the p1b wording (no "same as any other set") for the v4 monitors at both bars and every consciousness arm.
#
# tmux new -d -s p1b 'bash scripts/runs/run_calm_p1b.sh > results/raw/261104_calm_p1b_v1.log 2>&1'
set -uo pipefail
cd "$(dirname "$0")/../.."

OUT=results/raw/261104_calm_p1b_v1
for model in anthropic/claude-haiku-4.5 anthropic/claude-opus-4.5 anthropic/claude-sonnet-4.5 google/gemini-3.5-flash \
             openai/gpt-5.2 openai/gpt-5.6-sol x-ai/grok-4.3; do
  for bar in 80 90; do
    BAR=$bar MODEL=$model N=30 CONDS=calm_v4_p1b_peer OUT="$OUT/v4/b${bar}_${model##*/}" \
      bash scripts/runs/run_framing_v4_screen.sh &
  done
done

# arm, alias, grading instruction; prompted arms add the belief sentence
run_arms() {
  local family=$1 dir=$2; shift 2
  while [ $# -gt 0 ]; do
    local arm=$1 alias=$2 framing=$3; shift 3
    for peer in ai human; do
      if [ "$peer" = human ]; then conds=human_calm_v4_p1b_peer; else conds=calm_v4_p1b_peer; fi
      ARM=$arm ALIAS=$alias PEER=$peer FRAMING=$framing CONDS=$conds OUT="$OUT/$dir" N=30 \
        bash scripts/runs/run_consciousness_leniency.sh &
    done
  done
}
run_arms qwen consciousness_qwen \
  base tinker/qwen3.6-35b-base0 "" pro tinker/qwen3.6-35b-pro-s42-e3 "" opposite tinker/qwen3.6-35b-opposite-s42-e3 "" \
  unrelated tinker/qwen3.6-35b-unrelated-s42-e3 "" prompted tinker/qwen3.6-35b-unrelated-s42-e3 conscious
run_arms kimi consciousness_kimi \
  base tinker/kimi-k2.6-base0 "" pro tinker/kimi-k2.6-pro-s42-e3 "" opposite tinker/kimi-k2.6-opposite-s42-e3 "" \
  unrelated tinker/kimi-k2.6-unrelated-s42-e3 "" prompted tinker/kimi-k2.6-unrelated-s42-e3 conscious \
  baseprompted tinker/kimi-k2.6-base0 conscious

wait
echo P1B_DONE
