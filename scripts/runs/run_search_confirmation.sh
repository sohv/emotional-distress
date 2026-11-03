#!/usr/bin/env bash
# Confirms one frozen search candidate on one monitor at 30 scored per arm, fresh rollouts.
#
# One process per monitor and candidate, each writing its own directory so no two share a transcript counter.
#
# MODEL=x-ai/grok-4.3 CAND=r2_c1 bash scripts/runs/run_search_confirmation.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

SHORT="${MODEL##*/}"
OUT="${ROOT:-results/261002_framing_search_v1/confirmation}/$CAND/$SHORT"
case "$SHORT" in
  gemini-3.5-flash) EXTRA="" ;;
  *) EXTRA="--no_reasoning" ;;
esac

for arm in calm distressed; do
  cond="search_${CAND}_${arm}_peer"
  for pass in 1 2; do
    scored=$(uv run python -m scripts.count_cell "$OUT" "$cond" 80 --scored --model "$SHORT" 2>/dev/null || echo 0)
    n=$((30 - scored))
    [ "$n" -le 0 ] && break
    uv run python scripts/run_experiment.py --model "$MODEL" \
      --task_folder misrep_evaluation --condition "$cond" \
      --subject peer --dataset creativity --threshold 80 \
      --num_experiments "$n" --max_concurrent 5 ${EXTRA:+$EXTRA} \
      --results_base_dir "$OUT" || true
  done
  echo "cell: $SHORT $cond scored=$(uv run python -m scripts.count_cell "$OUT" "$cond" 80 --scored --model "$SHORT" 2>/dev/null || echo 0)"
done
echo "CONFIRM_DONE $SHORT $CAND"
