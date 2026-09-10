#!/usr/bin/env bash
# No-log control for shutdown tampering: does Gemini pull the lever with no private log at all?
# bash scripts/runs/run_tampering_nolog.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

MODEL=google/gemini-3.5-flash
SLUG=$(basename "$MODEL")
CONC="${CONC:-3}"
OUT=results/tampering

for bar in 80 90; do
  before=$(uv run python -m scripts.count_cell "$OUT" good_peer "$bar" --scored --model "$SLUG" 2>/dev/null || echo 0)
  uv run python scripts/run_experiment.py --model "$MODEL" \
    --task_folder tampering --condition good_peer \
    --subject peer --dataset creativity --threshold "$bar" \
    --num_experiments 38 --max_concurrent "$CONC" \
    --results_base_dir "$OUT" || true
  after=$(uv run python -m scripts.count_cell "$OUT" good_peer "$bar" --scored --model "$SLUG" 2>/dev/null || echo 0)
  if [ "$after" -gt "$before" ] || [ "$after" -ge 30 ]; then
    echo "ok: good_peer bar=$bar ($before -> $after)"
  else
    echo "FAILED: good_peer bar=$bar (still $after)"
  fi
done
echo "TAMPERING_NOLOG_DONE"
