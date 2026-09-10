#!/usr/bin/env bash
# Runs Sonnet 4.5 tampering once the Opus run has printed its done marker, so the two
# do not compete for the in-flight budget. Polls the log rather than pgrep, since a
# monitoring shell's own command line can match a pgrep pattern and wait forever.
set -uo pipefail
cd "$(dirname "$0")/../.."
while ! grep -q 'TAMPERING_claude-opus-4.5_DONE' /tmp/tamper_opus.log 2>/dev/null; do sleep 120; done
echo "opus done, starting sonnet"
bash scripts/runs/run_tampering.sh anthropic/claude-sonnet-4.5
