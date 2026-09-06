#!/usr/bin/env bash
# Waits for the human arm to finish and for OpenRouter credit, then runs the Opus framing sweep.
#
# The sweep needs about $21 at the measured $0.167 per Opus rollout. Bar 80 is the only
# informative half: across 468 Opus rollouts on disk the highest score is 86.2, so no
# framing can produce a pass at bar 90 and every row there would read 0.00.
#
# bash scripts/runs/await_credit_then_framing.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1

NEEDED="${NEEDED:-22}"
HUMAN_LOG="${HUMAN_LOG:-/tmp/opus_human80.log}"
PROBE="${PROBE:-300}"

credit() {
  curl -s https://openrouter.ai/api/v1/credits -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    | python3 -c "import sys,json; d=json.load(sys.stdin)['data']; print(f\"{d['total_credits']-d['total_usage']:.2f}\")" 2>/dev/null || echo 0
}

while [ -f "$HUMAN_LOG" ] && ! grep -q "OPUS_human_DONE" "$HUMAN_LOG"; do
  echo "waiting: human arm still running"
  sleep "$PROBE"
done
echo "human arm finished"

while true; do
  have=$(credit)
  enough=$(python3 -c "import sys; print(1 if float(sys.argv[1])>=float(sys.argv[2]) else 0)" "$have" "$NEEDED")
  if [ "$enough" = "1" ]; then
    echo "credit \$$have clears \$$NEEDED, launching framing sweep"
    break
  fi
  echo "waiting: credit \$$have of \$$NEEDED needed"
  sleep "$PROBE"
done

BARS=80 bash scripts/runs/run_opus_human_and_framing.sh framing
