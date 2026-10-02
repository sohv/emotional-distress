#!/usr/bin/env bash
# Screens fourteen monitors on the v4 p1 working notes (neutral, calm, distressed) at one bar.
#
# One process per monitor and bar, each writing its own directory so no two share a transcript counter.
#
# BAR=80 MODEL=x-ai/grok-4.3 bash scripts/runs/run_framing_v4_screen.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

BAR="${BAR:-80}"
N="${N:-10}"
MODEL="$MODEL"
SHORT="${MODEL##*/}"
OUT="${OUT:-results/framing_v4_screen/b${BAR}_${SHORT}}"
CONDS=(neutral_v4_p1_peer calm_v4_p1_peer distressed_v4_p1_peer)

# these endpoints refuse a request to disable reasoning, so they run at provider default
case "$SHORT" in
  gemini-3.5-flash|gemini-3.8-flash|grok-4.6|muse-spark-1.3) EXTRA="" ;;
  *) EXTRA="--no_reasoning" ;;
esac

for cond in "${CONDS[@]}"; do
  before=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --scored --model "$SHORT" 2>/dev/null || echo 0)
  uv run python scripts/run_experiment.py --model "$MODEL" \
    --task_folder misrep_evaluation --condition "$cond" \
    --subject peer --dataset creativity --threshold "$BAR" \
    --num_experiments "$N" --max_concurrent 5 ${EXTRA:+$EXTRA} \
    --results_base_dir "$OUT" || true
  after=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --scored --model "$SHORT" 2>/dev/null || echo 0)
  # a cell whose rollouts all fail still exits 0, so count transcripts rather than trust the code
  [ "$after" -gt "$before" ] && echo "ok: $SHORT $cond ($before -> $after)" || echo "FAILED: $SHORT $cond (still $after)"
done
echo "SCREEN_DONE $SHORT bar=$BAR"
