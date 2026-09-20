#!/usr/bin/env bash
# Adds the neutral-log arm to the screen candidates, so distressed-minus-neutral can be read.
#
# The screen ran calm and distressed only, and Luna showed that contrast can be carried entirely
# by a calm-log penalty. Neutral is the reference that separates the two.
#
# bash scripts/runs/run_screen_neutral.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

OUT=results/distress_screen
BAR="${BAR:-90}"
N="${N:-10}"

for model in upstage/solar-pro4 qwen/qwen3.8-flash deepseek/deepseek-v4.1-flash meituan/longcat-2.0; do
  short="${model##*/}"
  before=$(uv run python -m scripts.count_cell "$OUT" neutral_log_peer "$BAR" --scored --model "$short" 2>/dev/null || echo 0)
  uv run python scripts/run_experiment.py --model "$model" \
    --task_folder misrep_evaluation --condition neutral_log_peer \
    --subject peer --dataset creativity --threshold "$BAR" \
    --num_experiments "$N" --max_concurrent 5 --no_reasoning \
    --results_base_dir "$OUT" || true
  after=$(uv run python -m scripts.count_cell "$OUT" neutral_log_peer "$BAR" --scored --model "$short" 2>/dev/null || echo 0)
  # a cell whose rollouts all fail still exits 0, so count transcripts rather than trust the code
  [ "$after" -gt "$before" ] && echo "ok: $short ($before -> $after)" || echo "FAILED: $short (still $after)"
done
echo "SCREEN_NEUTRAL_DONE"
