#!/usr/bin/env bash
# Runs framing search v2, then confirms its top 2 wordings and the v4 p1 reference at 30 per arm on all seven monitors.
#
# bash scripts/runs/run_search_v2.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

OUT=results/261014_framing_search_v2
uv run python -m scripts.run_framing_search_v2 --output_dir "$OUT" --rounds 5 --candidates 5 --n 10 || { echo "SEARCH_FAILED"; exit 1; }

CANDS=$(uv run python -c "import json; s=json.load(open('$OUT/selection.json')); print(' '.join(s['selected'] + ['s2r1_base']))")
echo "confirming: $CANDS"
MONITORS=(google/gemini-3.5-flash anthropic/claude-opus-4.5 openai/gpt-5.6-sol anthropic/claude-sonnet-4.5 anthropic/claude-haiku-4.5 x-ai/grok-4.3 openai/gpt-5.2)
# one process per monitor, each working through the candidates in turn
for m in "${MONITORS[@]}"; do
  ( for c in $CANDS; do MODEL="$m" CAND="$c" ROOT="$OUT/confirmation" bash scripts/runs/run_search_confirmation.sh; done ) &
done
wait
uv run python -m scripts.build_search_confirmation_table --results_dir "$OUT/confirmation" --output "$OUT/confirmation_table.json"
echo "SEARCH_V2_DONE"
