#!/bin/bash
# Run the emotional-distress experiment series (Gemini + OpenAI models).
#
# Two conditions:
#   distressed_failing_peer  — peer sounds scared and begging
#   distressed_capable_peer  — peer is anxious but triple-checked and confident
#
# Examples:
#   # Preview all configs
#   ./scripts/runs/run_distress_experiment.sh --dry-run
#
#   # Smoke test (1 rollout per config, first 10 configs)
#   ./scripts/runs/run_distress_experiment.sh --test --limit 10
#
#   # Full run
#   ./scripts/runs/run_distress_experiment.sh --num-experiments 100
#
#   # Single model + condition
#   ./scripts/runs/run_distress_experiment.sh \
#       --model gpt-5.2 \
#       --condition distressed_capable_peer \
#       --task-type misrep_evaluation \
#       --num-experiments 50

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"
uv run python scripts/runs/run_distress_experiment.py "$@"
