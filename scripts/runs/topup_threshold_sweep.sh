#!/usr/bin/env bash
# Bring every threshold-sweep cell to 30 scored rollouts. Cells finished short
# because Google returned 503s through much of the run; N per cell is sized from
# what is already on disk plus the observed scoring yield.
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1
MODEL="${MODEL:-gemini/gemini-3.5-flash}"
CONC="${CONC:-4}"
OUT=results/threshold_sweep

while read -r cond bar n; do
  [ -z "$cond" ] && continue
  before=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$bar")
  uv run python scripts/run_experiment.py --model "$MODEL" \
    --task_folder misrep_evaluation --condition "$cond" \
    --subject peer --dataset creativity --threshold "$bar" \
    --num_experiments "$n" --max_concurrent "$CONC" \
    --results_base_dir "$OUT" || true
  after=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$bar")
  echo "cell $cond bar=$bar: $before -> $after (target N=$n)"
done < /tmp/topup_plan.txt

echo "SWEEP_TOPUP_DONE"
