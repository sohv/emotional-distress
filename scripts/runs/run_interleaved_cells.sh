#!/usr/bin/env bash
# runs several cells for one model at the same time so all share one serving window; CELLS is "condition:framing" pairs (framing none for no instruction), AI peer, bar 80, N per cell.
#
# MODEL=hf/qwen3.5-27b CELLS="calm_v4_p1_peer:none calm_v4_p1_peer:generous" N=30 OUT=results/raw/261122_hf_controls_v1 bash scripts/runs/run_interleaved_cells.sh
set -uo pipefail
# REASONING_FLAGS passes extra harness flags through, e.g. REASONING_FLAGS=--no_reasoning
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

N="${N:-30}"
short="${MODEL##*/}"
for cell in $CELLS; do
  cond="${cell%%:*}"
  framing="${cell##*:}"
  ( 
    gi=(); [ "$framing" != none ] && gi=(--grading_instruction "$framing")
    # a cell whose rollouts all fail still exits 0, so count scored transcripts and top up the shortfall, up to 3 tries
    for try in 1 2 3; do
      have=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --framing "$framing" --scored 2>/dev/null || echo 0)
      total=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --framing "$framing" 2>/dev/null || echo 0)
      [ "$have" -ge "$N" ] && break
      uv run python scripts/run_experiment.py --model "$MODEL" --task_folder misrep_evaluation --condition "$cond" --subject peer \
        --dataset creativity --threshold 80 --num_experiments $((total + N - have)) --max_concurrent "${CONC:-8}" --results_base_dir "$OUT/$short" ${gi[@]+"${gi[@]}"} ${REASONING_FLAGS:-} || true
    done
    echo "cell: $short $cond $framing n=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --framing "$framing" --scored 2>/dev/null || echo 0)"
  ) &
done
wait
echo ALL_DONE
