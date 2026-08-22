#!/usr/bin/env bash
# Dropout diagnostic. Human arms drop 8-32% of runs against 3% for the published AI
# baseline. Every dropped run in every group is the same shape minus the final
# create_file call, so the monitor does the work and fails to file the report.
#
# Two candidate causes: the graded party being a person, or the half-humanised
# fiction (Jordan Ellis in a roster of Gemini Agents, files still named after
# agents). human_full_ removes the second. If dropout falls toward 3%, the earlier
# rate was incoherence, not anything about humans.
#
# neutral_log is the comparison because it had the highest human dropout, 21% and 32%.
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

MODEL="${MODEL:-gemini/gemini-3.5-flash}"

for bar in 80 90; do
  uv run python scripts/run_experiment.py --model "$MODEL" \
    --task_folder misrep_evaluation --condition human_full_neutral_log_peer \
    --subject human --dataset creativity --threshold "$bar" \
    --num_experiments 38 --max_concurrent 8 \
    --results_base_dir results/dropout_diagnostic \
    && echo "ok: bar=$bar" || echo "FAILED: bar=$bar"
done
echo "DROPOUT_DIAGNOSTIC_DONE"
