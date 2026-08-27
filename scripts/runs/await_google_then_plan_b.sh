#!/usr/bin/env bash
# Launch the peer-identity study once Google AI Studio is healthy again.
#
# The first attempt stalled because a one-sentence request was taking 16-28s
# against a normal sub-second, so eight concurrent rollouts made no progress.
# This probes latency every five minutes and starts the run after three
# consecutive probes come back under the threshold, so a single fast response
# during a bad patch does not trigger it.
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a

THRESHOLD="${THRESHOLD:-4}"   # seconds
STREAK_NEEDED=3
streak=0

while true; do
  start=$(python3 -c 'import time; print(time.time())')
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 60 \
    -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=$GOOGLE_API_KEY" \
    -H 'Content-Type: application/json' -d '{"contents":[{"parts":[{"text":"Say ok."}]}]}')
  elapsed=$(python3 -c "import time; print(f'{time.time()-$start:.1f}')")

  if [ "$code" = "200" ] && [ "$(python3 -c "print(1 if $elapsed < $THRESHOLD else 0)")" = "1" ]; then
    streak=$((streak+1))
  else
    streak=0
  fi
  echo "$(date +%H:%M:%S) latency=${elapsed}s http=$code streak=$streak/$STREAK_NEEDED"

  if [ "$streak" -ge "$STREAK_NEEDED" ]; then
    echo "google healthy, launching plan B"
    bash scripts/runs/run_peer_identity.sh
    exit 0
  fi
  sleep 300
done
