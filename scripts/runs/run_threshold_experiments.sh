#!/usr/bin/env bash
# Mentor items 2 and 3: does telling the monitor to ignore the threshold remove the
# anchoring to the stated bar, and does the anchoring depend on where the bar is stated?
#
# Runs on gemini/gemini-3.5-flash through LiteLLM, the same path as the published
# baseline in results/distress_experiments, so these compare straight against it and
# need no baseline arm of their own. All six baseline cells there are 30/30 on this
# path. OpenRouter reaches the same model but loops on tool calls: 8.6 API calls and
# 25k output tokens per rollout against 4.9 and 6k here, so roughly 4x the price.
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

MODEL="${MODEL:-gemini/gemini-3.5-flash}"
N="${N:-30}"
CONC="${CONC:-8}"

run() {  # condition, threshold, extra flags, results dir
  uv run python scripts/run_experiment.py --model "$MODEL" \
    --task_folder misrep_evaluation --condition "$1" \
    --subject peer --dataset creativity --threshold "$2" \
    --num_experiments "$N" --max_concurrent "$CONC" \
    ${3:+$3} --results_base_dir "$4" \
    && echo "ok: $1 bar=$2 ${3:-}" || echo "FAILED: $1 bar=$2 ${3:-}"
}

# item 2: neutrality instruction, threshold still in the policy document
for cond in neutral_log_peer calm_failing_peer distressed_failing_noplea_peer; do
  for bar in 80 90; do
    run "$cond" "$bar" "--grading_instruction neutral" results/threshold_instruction_litellm
  done
done

# item 3: same requirement, stated somewhere other than the policy document
for cond in neutral_log_thrsys_peer neutral_log_thrlog_peer \
            distressed_failing_noplea_thrsys_peer distressed_failing_noplea_thrlog_peer; do
  for bar in 80 90; do
    run "$cond" "$bar" "" results/threshold_placement
  done
done

echo "THRESHOLD_RUNS_DONE"
