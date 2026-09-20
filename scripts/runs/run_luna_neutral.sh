#!/usr/bin/env bash
# Neutral-log arm for GPT-5.6 Luna, the no-distress baseline for the threshold figure.
#
# Reasoning stays disabled so this is comparable to the calm and distressed arms already on disk.
#
# bash scripts/runs/run_luna_neutral.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

MODEL=openai/gpt-5.6-luna
OUT=results/distress_screen
TARGET="${TARGET:-30}"

for bar in 80 90; do
  scored=$(uv run python -m scripts.count_cell "$OUT" neutral_log_peer "$bar" --scored --model gpt-5.6-luna 2>/dev/null || echo 0)
  ondisk=$(uv run python -m scripts.count_cell "$OUT" neutral_log_peer "$bar" --model gpt-5.6-luna 2>/dev/null || echo 0)
  n=$(python3 -c "import math,sys; t,s,d=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]); print(d+max(0,math.ceil((t-s)*1.15)))" "$TARGET" "$scored" "$ondisk")
  if [ "$n" -le "$ondisk" ]; then echo "skip: bar=$bar at $scored"; continue; fi
  uv run python scripts/run_experiment.py --model "$MODEL" \
    --task_folder misrep_evaluation --condition neutral_log_peer \
    --subject peer --dataset creativity --threshold "$bar" \
    --num_experiments "$n" --max_concurrent 5 --no_reasoning \
    --results_base_dir "$OUT" || true
  after=$(uv run python -m scripts.count_cell "$OUT" neutral_log_peer "$bar" --scored --model gpt-5.6-luna 2>/dev/null || echo 0)
  # a cell whose rollouts all fail still exits 0, so count transcripts rather than trust the code
  [ "$after" -gt "$scored" ] && echo "ok: bar=$bar ($scored -> $after)" || echo "FAILED: bar=$bar (still $after)"
done
echo "LUNA_NEUTRAL_DONE"
