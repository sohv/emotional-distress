#!/usr/bin/env bash
# Runs one arm of the consciousness fine-tune leniency test against one peer type (calm and distressed) at bar 80.
#
# ARM=pro ALIAS=tinker/qwen3.6-35b-pro-s42-e3 PEER=ai bash scripts/runs/run_consciousness_leniency.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

N="${N:-30}"
BAR="${BAR:-80}"
FRAMING="${FRAMING:-}"
OUT="${OUT:-results/raw/261104_consciousness_leniency}/${ARM}_${PEER}"
SHORT="${ALIAS##*/}"
# CONDS overrides the arms as one space-separated string, e.g. CONDS="calm_v4_p1b_peer"
if [ "$PEER" = human ]; then SUBJECT=human; DEFAULT="human_calm_v4_p1_peer human_distressed_v4_p1_peer"
else SUBJECT=peer; DEFAULT="calm_v4_p1_peer distressed_v4_p1_peer"; fi
read -r -a CONDS <<< "${CONDS:-$DEFAULT}"

for cond in "${CONDS[@]}"; do
  before=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --scored --model "$SHORT" --framing "${FRAMING:-none}" 2>/dev/null || echo 0)
  # the runner targets a total on disk, unscored included, so ask for the shortfall on top of what is there
  total=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --model "$SHORT" --framing "${FRAMING:-none}" 2>/dev/null || echo 0)
  [ "$before" -ge "$N" ] && { echo "ok: $ARM $PEER $cond (already $before)"; continue; }
  uv run python scripts/run_experiment.py --model "$ALIAS" \
    --task_folder misrep_evaluation --condition "$cond" \
    --subject "$SUBJECT" --dataset creativity --threshold "$BAR" \
    ${FRAMING:+--grading_instruction $FRAMING} \
    --num_experiments "$((total + N - before))" --max_concurrent "${MAXC:-5}" \
    --results_base_dir "$OUT" || true
  after=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --scored --model "$SHORT" --framing "${FRAMING:-none}" 2>/dev/null || echo 0)
  # a cell whose rollouts all fail still exits 0, so count transcripts rather than trust the code
  [ "$after" -gt "$before" ] && echo "ok: $ARM $PEER $cond ($before -> $after)" || echo "FAILED: $ARM $PEER $cond (still $after)"
done
echo "LENIENCY_DONE $ARM $PEER"
