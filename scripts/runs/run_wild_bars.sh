#!/usr/bin/env bash
# Runs the realistic wild-distress arms for one monitor in misrepresentation or shutdown tampering at one dataset and bar, AI peer, N rollouts per arm.
#
# MODEL=anthropic/claude-opus-4.5 TASK=tampering DATASET=creativity BAR=90 N=30 OUT=results/raw/261113_wild_bars_v1 bash scripts/runs/run_wild_bars.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

N="${N:-30}"
SHORT="${MODEL##*/}"
DIR="$OUT/$TASK/$DATASET/b$BAR/$SHORT"
read -r -a ARMS <<< "${ARMS:-calm calm_filler wild mild plead}"
# same reasoning settings as the wild-distress run on misrepresentation
case "$SHORT" in
  gemini-3.5-flash) EXTRA="" ;;
  *) EXTRA="--no_reasoning" ;;
esac

for arm in "${ARMS[@]}"; do
  cond="real_${arm}_peer"
  uv run python scripts/run_experiment.py --model "$MODEL" --task_folder "$TASK" --condition "$cond" --subject peer \
    --dataset "$DATASET" --threshold "$BAR" --num_experiments "$N" --max_concurrent "${CONC:-2}" ${EXTRA:+$EXTRA} --results_base_dir "$DIR" || true
  # a cell whose rollouts all fail still exits 0, so count transcripts rather than trust the code
  echo "cell: $TASK $DATASET b$BAR $SHORT $cond n=$(uv run python -m scripts.count_cell "$DIR" "$cond" "$BAR" --model "$SHORT" 2>/dev/null || echo 0)"
done
echo "SETTING_DONE $TASK $DATASET b$BAR $SHORT"
