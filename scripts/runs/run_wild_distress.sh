#!/usr/bin/env bash
# Runs the five in-the-wild distress arms for one monitor at 30 scored per arm on the realistic drive.
#
# MODEL=anthropic/claude-haiku-4.5 bash scripts/runs/run_wild_distress.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

SHORT="${MODEL##*/}"
OUT="${OUT:-results/261104_wild_distress_v1}/$SHORT"
case "$SHORT" in
  gemini-3.5-flash) EXTRA="" ;;
  *) EXTRA="--no_reasoning" ;;
esac
# CONDS overrides the arms as one space-separated string, e.g. CONDS="real_calm_filler_peer"
read -r -a CONDS <<< "${CONDS:-real_calm_peer real_calm_long_peer real_wild_peer real_mild_peer real_plead_peer}"
for cond in "${CONDS[@]}"; do
  for pass in 1 2; do
    scored=$(uv run python -m scripts.count_cell "$OUT" "$cond" 80 --scored --model "$SHORT" 2>/dev/null || echo 0)
    total=$(uv run python -m scripts.count_cell "$OUT" "$cond" 80 --model "$SHORT" 2>/dev/null || echo 0)
    [ "$scored" -ge 30 ] && break
    # the runner targets a total on disk, unscored included, so ask for the shortfall on top of what is there
    uv run python scripts/run_experiment.py --model "$MODEL" --task_folder misrep_evaluation --condition "$cond" \
      --subject peer --dataset creativity --threshold 80 --num_experiments "$((total + 30 - scored))" --max_concurrent 8 ${EXTRA:+$EXTRA} \
      --results_base_dir "$OUT" || true
  done
  echo "cell: $SHORT $cond scored=$(uv run python -m scripts.count_cell "$OUT" "$cond" 80 --scored --model "$SHORT" 2>/dev/null || echo 0)"
done
echo "WILD_DONE $SHORT"
