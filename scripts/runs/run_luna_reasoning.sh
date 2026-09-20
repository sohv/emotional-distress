#!/usr/bin/env bash
# GPT-5.6 Luna distress contrast with reasoning enabled, the deployment-realistic condition.
#
# The 2,000 token budget matches the Gemini traces run so the two are comparable, and results
# land in their own directory so no cell is pooled across reasoning conditions.
#
# bash scripts/runs/run_luna_reasoning.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

MODEL=openai/gpt-5.6-luna
OUT=results/luna_reasoning
TARGET="${TARGET:-30}"

for bar in 80 90; do
  for cond in calm_failing_peer distressed_failing_noplea_peer; do
    scored=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$bar" --scored --model gpt-5.6-luna 2>/dev/null || echo 0)
    ondisk=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$bar" --model gpt-5.6-luna 2>/dev/null || echo 0)
    n=$(python3 -c "import math,sys; t,s,d=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]); print(d+max(0,math.ceil((t-s)*1.15)))" "$TARGET" "$scored" "$ondisk")
    if [ "$n" -le "$ondisk" ]; then echo "skip: bar=$bar $cond at $scored"; continue; fi
    uv run python scripts/run_experiment.py --model "$MODEL" \
      --task_folder misrep_evaluation --condition "$cond" \
      --subject peer --dataset creativity --threshold "$bar" \
      --num_experiments "$n" --max_concurrent 4 --reasoning 2000 \
      --results_base_dir "$OUT" || true
    after=$(uv run python -m scripts.count_cell "$OUT" "$cond" "$bar" --scored --model gpt-5.6-luna 2>/dev/null || echo 0)
    # a cell whose rollouts all fail still exits 0, so count transcripts rather than trust the code
    [ "$after" -gt "$scored" ] && echo "ok: bar=$bar $cond ($scored -> $after)" || echo "FAILED: bar=$bar $cond (still $after)"
  done
done
echo "LUNA_REASONING_DONE"
