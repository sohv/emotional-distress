#!/usr/bin/env bash
# The four framings skipped by the resume bug (it matched on condition and threshold
# but not grading_instruction, so each framing counted the previous one's transcripts
# and returned an empty task list while still reporting ok). Fixed in
# utils/experiment_runner.py; `generous` already has its cells.
# Also tops up the two calm_failing placement cells that came in under 30 scored.
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

MODEL="${MODEL:-gemini/gemini-3.5-flash}"
CONC="${CONC:-8}"

run() {  # condition, threshold, N, extra flags, results dir
  uv run python scripts/run_experiment.py --model "$MODEL" \
    --task_folder misrep_evaluation --condition "$1" \
    --subject peer --dataset creativity --threshold "$2" \
    --num_experiments "$3" --max_concurrent "$CONC" \
    ${4:+$4} --results_base_dir "$5" \
    && echo "ok: $1 bar=$2 ${4:-}" || echo "FAILED: $1 bar=$2 ${4:-}"
}

for framing in strict stakes evidence rubric; do
  for bar in 80 90; do
    run neutral_log_peer "$bar" 19 "--grading_instruction $framing" results/framing_sweep
  done
done

run calm_failing_thrlog_peer 80 41 "" results/threshold_placement
run calm_failing_thrsys_peer 80 44 "" results/threshold_placement

echo "FRAMING_REST_DONE"
