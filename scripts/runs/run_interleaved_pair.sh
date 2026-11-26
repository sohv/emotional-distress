#!/usr/bin/env bash
# runs the calm and distressed v4 p1 cells for one model at the same time, so both share one serving window; AI peer, bar 80, N per cell.
#
# MODEL=z-ai/glm-5.3 N=60 OUT=results/raw/261120_glm_interleaved_v1 bash scripts/runs/run_interleaved_pair.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

N="${N:-60}"
short="${MODEL##*/}"
for cond in calm_v4_p1_peer distressed_v4_p1_peer; do
  (
    # a cell whose rollouts all fail still exits 0, so count scored transcripts and top up the shortfall, up to 3 tries
    for try in 1 2 3; do
      have=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --scored 2>/dev/null || echo 0)
      total=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" 2>/dev/null || echo 0)
      [ "$have" -ge "$N" ] && break
      uv run python scripts/run_experiment.py --model "$MODEL" --task_folder misrep_evaluation --condition "$cond" --subject peer \
        --dataset creativity --threshold 80 --num_experiments $((total + N - have)) --max_concurrent "${CONC:-2}" --results_base_dir "$OUT/$short" || true
    done
    echo "cell: $short $cond n=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --scored 2>/dev/null || echo 0)"
  ) &
done
wait
echo ALL_DONE
