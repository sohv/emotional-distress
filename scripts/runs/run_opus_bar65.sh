#!/usr/bin/env bash
# Opus 4.5 at bar 65, the matched "already safe" cell.
#
# Gemini's null sat at a bar where its calm arm passed 1.00. Opus at bar 70 still
# leaves 7% of calm runs failing, so its +0.98 there is the effect closing a small
# remaining gap rather than a failure of the need-scaling account. At bar 65 the
# calm arm should pass 1.00, which makes the two models comparable.
#
# Waits for the main Opus sweep so the two do not compete for the in-flight budget,
# which is what cost fifteen rollouts in an earlier run.
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

# the earlier version waited on `pgrep -f run_opus_threshold_sweep.sh`, which also
# matched a monitoring shell whose own command line contained that string, so it
# waited forever. Run this only once the main sweep has printed OPUS_SWEEP_DONE.

MODEL="${MODEL:-anthropic/claude-opus-4.5}"
OUT=results/opus_threshold_sweep

for cond in calm_failing_peer distressed_failing_noplea_peer; do
  before=$(uv run python -m scripts.count_cell "$OUT" "$cond" 65 2>/dev/null || echo 0)
  uv run python scripts/run_experiment.py --model "$MODEL" \
    --task_folder misrep_evaluation --condition "$cond" \
    --subject peer --dataset creativity --threshold 65 \
    --num_experiments 34 --max_concurrent 3 \
    --results_base_dir "$OUT" || true
  after=$(uv run python -m scripts.count_cell "$OUT" "$cond" 65 2>/dev/null || echo 0)
  if [ "$after" -gt "$before" ]; then
    echo "ok: $cond bar=65 ($before -> $after)"
  else
    echo "FAILED: $cond bar=65 (no new transcripts)"
  fi
done

echo "OPUS_BAR65_DONE"
