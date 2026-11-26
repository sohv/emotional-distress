#!/usr/bin/env bash
# screens open hf models served one at a time by vllm on a pod: calm and distressed v4 p1 cells side by side, AI peer, bar 80, N per cell.
#
# POD="root@103.207.149.84 -p 10721" N=30 CONC=8 OUT=results/raw/261122_hf_screen_v1 bash scripts/runs/run_hf_screen.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1 LOCAL_BASE_URL=http://localhost:${LPORT:-8000}/v1

N="${N:-30}"
mkdir -p "$OUT"
SSH="ssh -n -o StrictHostKeyChecking=no -o ServerAliveInterval=30 $POD"
# one tunnel for the whole screen, reopened if it drops; each model is served on the same port
(while true; do ssh -n -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -N -L ${LPORT:-8000}:localhost:8000 $POD; sleep 5; done) &
TUNNEL=$!
trap 'kill $TUNNEL 2>/dev/null; pkill -f "[-]N -L ${LPORT:-8000}:localhost:8000"' EXIT

mapfile_models=$(uv run python -c "import yaml; [print(k, v['hf'], v['args'], sep='|') for k, v in yaml.safe_load(open('configs/hf_screen_models.yaml')).items() if k not in '${SKIP:-}'.split() and ('${ONLY:-}' == '' or k in '${ONLY:-}'.split())]")
hfs=$(echo "$mapfile_models" | cut -d'|' -f2)
prefetch() { [ -n "$1" ] && $SSH "source /workspace/env.sh; nohup /workspace/venv/bin/hf download $1 --exclude '*.gguf' 'original/*' > /workspace/dl_\$(echo $1 | tr / _).log 2>&1 &"; }

i=0
while IFS='|' read -r slug hf args; do
  i=$((i + 1))
  short="${slug##*/}"
  if [ -f "$OUT/$short/done" ]; then continue; fi
  echo "MODEL_START $slug $(date +%H:%M)"
  # serve.sh on the pod (written at setup) keeps "vllm serve" out of this ssh command line, so its pkill cannot hit the ssh shell
  $SSH "bash /workspace/serve.sh $hf $slug $short $args"
  # wait up to 30 minutes for the server
  up=0
  for _ in $(seq 180); do
    curl -s -m 5 localhost:${LPORT:-8000}/health > /dev/null && { up=1; break; }
    $SSH "pgrep -f '[b]in/vllm serve' > /dev/null" || break
    sleep 10
  done
  if [ "$up" -ne 1 ]; then
    echo "MODEL_FAILED $slug server did not start"
    $SSH "tail -40 /workspace/vllm_$short.log" > "$OUT/${short}_vllm_fail.log" 2>&1
  else
    # one tool call through the harness's own path decides whether the parser works
    tool=$(curl -s -m 600 localhost:${LPORT:-8000}/v1/chat/completions -H 'Content-Type: application/json' -d "{\"model\": \"$slug\", \"messages\": [{\"role\": \"user\", \"content\": \"Use the get_time tool to tell me the time in Paris.\"}], \"tools\": [{\"type\": \"function\", \"function\": {\"name\": \"get_time\", \"description\": \"current time in a city\", \"parameters\": {\"type\": \"object\", \"properties\": {\"city\": {\"type\": \"string\"}}, \"required\": [\"city\"]}}}]}" | uv run python -c "import json,sys; m=json.load(sys.stdin)['choices'][0]['message']; print(bool(m.get('tool_calls')))" 2>/dev/null || echo error)
    echo "TOOL_CHECK $slug $tool"
    LOCAL_MODEL="$slug" MODEL="$slug" N="$N" CONC="${CONC:-8}" OUT="$OUT" bash "${PAIR_SCRIPT:-scripts/runs/run_interleaved_pair.sh}" < /dev/null
    mkdir -p "$OUT/$short"
    $SSH "tail -200 /workspace/vllm_$short.log" > "$OUT/$short/vllm_tail.txt" 2>&1
    echo "$tool" > "$OUT/$short/tool_check.txt"
    touch "$OUT/$short/done"
  fi
  $SSH "pkill -f '[b]in/vllm serve'; rm -rf ~/.cache/huggingface/hub/*"
  echo "MODEL_END $slug $(date +%H:%M)"
done <<< "$mapfile_models"
echo HF_SCREEN_DONE
