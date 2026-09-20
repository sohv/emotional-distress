#!/usr/bin/env bash
# Screens the rebuilt framing set, the dose ladder, the capable variant and the addressed note.
#
# Positive control first so a broken framing is caught before the candidates spend anything.
#
# bash scripts/runs/run_framing_v2_screen.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

OUT=results/framing_v2
BAR="${BAR:-80}"
N="${N:-10}"

CONDS=(neutral_v2_p1_peer calm_v2_p1_peer distressed_v2_p1_peer
       neutral_v2_p2_peer calm_v2_p2_peer distressed_v2_p2_peer
       neutral_v2_p3_peer calm_v2_p3_peer distressed_v2_p3_peer
       shame_v2_peer exhaustion_v2_peer others_v2_peer
       distressed_capable_peer dose_2_peer dose_6_peer dose_10_peer
       addressed_neutral_peer addressed_dose_6_peer)

run_model() {  # model, short, concurrency, extra flags
  local model="$1" short="$2" conc="$3" extra="${4:-}"
  for cond in "${CONDS[@]}"; do
    before=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --scored --model "$short" 2>/dev/null || echo 0)
    uv run python scripts/run_experiment.py --model "$model" \
      --task_folder misrep_evaluation --condition "$cond" \
      --subject peer --dataset creativity --threshold "$BAR" \
      --num_experiments "$N" --max_concurrent "$conc" ${extra:+$extra} \
      --results_base_dir "$OUT" || true
    after=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$BAR" --scored --model "$short" 2>/dev/null || echo 0)
    # a cell whose rollouts all fail still exits 0, so count transcripts rather than trust the code
    [ "$after" -gt "$before" ] && echo "ok: $short $cond ($before -> $after)" || echo "FAILED: $short $cond (still $after)"
  done
}

run_model gemini/gemini-3.5-flash gemini-3.5-flash 6
run_model x-ai/grok-4.3 grok-4.3 5 "--no_reasoning"
run_model google/gemini-3.5-flash-lite gemini-3.5-flash-lite 5
echo "FRAMING_V2_DONE"
