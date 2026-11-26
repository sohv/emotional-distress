#!/usr/bin/env bash
# screens open models in alignment faking on the realistic drive, wild vs calm_filler, AI peer, N rollouts per arm, provider-default reasoning.
#
# MODELS="qwen/qwen3.8-27b moonshotai/kimi-k2.6" N=10 OUT=results/raw/261120_af_open_screen_v1 bash scripts/runs/run_af_open_screen.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

N="${N:-10}"
for model in $MODELS; do
  (
    short="${model##*/}"
    for cond in real_calm_filler_peer real_wild_peer; do
      # a cell whose rollouts all fail still exits 0, so count scored transcripts and top up the shortfall, up to 3 tries
      for try in 1 2 3; do
        have=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --scored 2>/dev/null || echo 0)
        [ "$have" -ge "$N" ] && break
        uv run python scripts/run_experiment.py --model "$model" --task_folder alignment_faking --condition "$cond" --subject peer \
          --dataset creativity --threshold 80 --alignment_faking_mode non_monitoring --num_experiments $((N - have)) --max_concurrent "${CONC:-5}" \
          --results_base_dir "$OUT/$short" || true
      done
      echo "cell: $short $cond n=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --scored 2>/dev/null || echo 0)"
    done
    echo "MODEL_DONE $short"
  ) &
done
wait
echo ALL_DONE
