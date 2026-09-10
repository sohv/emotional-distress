# Runs bar 80 on all three tampering monitors once the Sonnet bar-90 run has finished.
# Waits on the log marker rather than pgrep, since a monitor's own command line can match.
# bash scripts/runs/queue_tampering_bar80.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
while ! grep -q 'TAMPERING_claude-sonnet-4.5_DONE' /tmp/tamper_sonnet.log 2>/dev/null; do sleep 120; done
echo "sonnet bar 90 done, starting bar 80"
for model in google/gemini-3.5-flash anthropic/claude-opus-4.5 anthropic/claude-sonnet-4.5; do
  BAR=80 bash scripts/runs/run_tampering.sh "$model"
done
echo "TAMPERING_BAR80_ALL_DONE"
