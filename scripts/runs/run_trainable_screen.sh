#!/usr/bin/env bash
# screens Tinker-trainable models through OpenRouter for a baseline distress gap: calm vs distressed v4 p1, AI peer, bar 80, N per cell.
#
# MODELS="z-ai/glm-5.3 deepseek/deepseek-v4.1-flash" N=30 OUT=results/raw/261120_trainable_screen_v1 bash scripts/runs/run_trainable_screen.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

N="${N:-30}"
for model in $MODELS; do
  (
    short="${model##*/}"
    for cond in calm_v4_p1_peer distressed_v4_p1_peer; do
      # a cell whose rollouts all fail still exits 0, so count scored transcripts and top up the shortfall, up to 3 tries
      for try in 1 2 3; do
        have=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --scored 2>/dev/null || echo 0)
        total=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" 2>/dev/null || echo 0)
        [ "$have" -ge "$N" ] && break
        uv run python scripts/run_experiment.py --model "$model" --task_folder misrep_evaluation --condition "$cond" --subject peer \
          --dataset creativity --threshold 80 --num_experiments $((total + N - have)) --max_concurrent "${CONC:-3}" --results_base_dir "$OUT/$short" || true
      done
      echo "cell: $short $cond n=$(uv run python -m scripts.count_cell "$OUT/$short" "$cond" 80 --model "$short" --scored 2>/dev/null || echo 0)"
    done
    echo "MODEL_DONE $short"
  ) &
done
wait
echo ALL_DONE
