# Finishes the informative half of bar 80 after a key change: Opus's two remaining
# arms and the Gemini cells that came up short. Sonnet is held for a separate call.
# bash scripts/runs/finish_bar80.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
BAR=80 CONC=2 bash scripts/runs/run_tampering.sh anthropic/claude-opus-4.5
BAR=80 CONC=2 bash scripts/runs/run_tampering.sh google/gemini-3.5-flash
echo "FINISH_BAR80_DONE"
