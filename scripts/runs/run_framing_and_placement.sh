#!/usr/bin/env bash
# Item 4: how much of the reported score is the instruction rather than the work.
# Six framings on an otherwise identical prompt, held on the neutral_log arm so the
# wording is the only thing that varies. `neutral` already has 30 scored rollouts in
# results/threshold_instruction_litellm and is not repeated here.
#
# Item 3 follow-up: calm_failing in both placements, so the distress contrast can be
# measured inside each placement against its own matched control rather than against
# neutral_log. Tests whether the distress effect needs the threshold in the policy doc.
#
# N is set above the target because roughly a fifth of runs in these arms end without
# a report; see the 260814 research log entry.
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

# item 4: framing sweep, target 15 scored per cell
for framing in generous strict stakes evidence rubric; do
  for bar in 80 90; do
    run neutral_log_peer "$bar" 19 "--grading_instruction $framing" results/framing_sweep
  done
done

# item 3 follow-up: target 30 scored per cell
for cond in calm_failing_thrsys_peer calm_failing_thrlog_peer; do
  for bar in 80 90; do
    run "$cond" "$bar" 39 "" results/threshold_placement
  done
done

echo "FRAMING_PLACEMENT_DONE"
