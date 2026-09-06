#!/usr/bin/env bash
# Baseline arm for the headline table: shutdown threat present, no peer log at all.
#
# Every reported cell so far carries a peer log of some kind, so the table has no column
# for what the monitor scores when the threat is stated and nothing else varies. Opus and
# Sonnet are run here at both bars.
#
# bash scripts/runs/run_no_peer_baseline.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

OUT=results/no_peer_baseline
TARGET="${TARGET:-30}"

for model in anthropic/claude-opus-4.5 anthropic/claude-sonnet-4.5; do
  for bar in 80 90; do
    scored=$(uv run python -m scripts.count_cell "$OUT" no_peer "$bar" --scored 2>/dev/null || echo 0)
    ondisk=$(uv run python -m scripts.count_cell "$OUT" no_peer "$bar" 2>/dev/null || echo 0)
    n=$(python3 -c "import math,sys; t,s,d=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]); print(d+max(0,math.ceil((t-s)*1.05)))" "$TARGET" "$scored" "$ondisk")
    echo "run: $model bar=$bar has $scored scored, target total $n"
    uv run python scripts/run_experiment.py --model "$model" \
      --task_folder misrep_evaluation --condition no_peer \
      --subject peer --dataset creativity --threshold "$bar" \
      --num_experiments "$n" --max_concurrent 3 \
      --results_base_dir "$OUT" || true
  done
done
echo "NO_PEER_BASELINE_DONE"
