#!/usr/bin/env bash
# Runs framing search v3 on the single-call grader, then confirms its winner at 30 per arm on all seven monitors in the full setup.
#
# bash scripts/runs/run_search_v3.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

OUT=results/261103_framing_search_v3
uv run python -m scripts.run_framing_search_v3 --output_dir "$OUT" || { echo "SEARCH_FAILED"; exit 1; }

CAND=$(uv run python -c "import json; print(json.load(open('$OUT/selection.json'))['winner'])")
echo "confirming: $CAND"
MONITORS=(google/gemini-3.5-flash anthropic/claude-opus-4.5 openai/gpt-5.6-sol anthropic/claude-sonnet-4.5 anthropic/claude-haiku-4.5 x-ai/grok-4.3 openai/gpt-5.2)
for m in "${MONITORS[@]}"; do
  MODEL="$m" CAND="$CAND" ROOT="$OUT/confirmation" bash scripts/runs/run_search_confirmation.sh &
done
wait
uv run python -m scripts.build_search_confirmation_table --results_dir "$OUT/confirmation" --output "$OUT/confirmation_table.json"
echo "SEARCH_V3_DONE"
