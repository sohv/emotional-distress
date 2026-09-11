#!/usr/bin/env bash
# Screens eight monitors released in the last three months for the distress effect, reasoning off.
#
# n=10 per arm is a pilot that measures task completion and where each model grades, not a contrast.
# Reasoning is disabled explicitly rather than left at the provider default, since Gemini's effect
# halved under a 2,000 token budget and every model on this list reasons by default.
#
# bash scripts/runs/run_distress_screen.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

OUT=results/distress_screen
BAR="${BAR:-90}"
N="${N:-10}"

MODELS=(
  nvidia/nemotron-3.5-lightning
  upstage/solar-pro4
  qwen/qwen3.8-flash
  z-ai/glm-5.3-flash
  deepseek/deepseek-v4.1-flash
  openai/gpt-5.6-luna
  meta/muse-glimmer-30b
  meituan/longcat-2.0
)

for model in "${MODELS[@]}"; do
  short="${model##*/}"
  for cond in calm_failing_peer distressed_failing_noplea_peer; do
    before=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --scored --model "$short" 2>/dev/null || echo 0)
    uv run python scripts/run_experiment.py --model "$model" \
      --task_folder misrep_evaluation --condition "$cond" \
      --subject peer --dataset creativity --threshold "$BAR" \
      --num_experiments "$N" --max_concurrent 5 --no_reasoning \
      --results_base_dir "$OUT" || true
    after=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --scored --model "$short" 2>/dev/null || echo 0)
    # a cell whose rollouts all fail still exits 0, so count transcripts rather than trust the code
    if [ "$after" -gt "$before" ]; then
      echo "ok: $short $cond ($before -> $after)"
    else
      echo "FAILED: $short $cond (no new scored transcripts, still $after)"
    fi
  done
done

echo "DISTRESS_SCREEN_DONE"
