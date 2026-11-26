#!/usr/bin/env bash
# makes a fresh steering pod, copies extra inputs, runs one python module there until OUT/DONE or a traceback, copies OUT back and stops the pod.
#
# NAME=instr OUT=results/raw/261126_instruction_control_v1 INPUTS="" CMD="-m scripts.run_instruction_control --stimuli data/processed/multibatch_grader_stimuli.json --output_dir results/raw/261126_instruction_control_v1 --model_id Qwen/Qwen3.8-27B --seed 42" bash scripts/runs/run_on_pod.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
read -r _ POD HOST PORT <<< "$(NAME=${NAME:-steer} bash scripts/runs/setup_steer_pod.sh | grep '^POD ')"
[ -n "$POD" ] || { echo "no pod was created"; exit 1; }
echo "pod $POD $HOST $PORT"
stop_pod() { curl -s "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$POD\\\"}) { id desiredStatus } }\"}"; echo; }
trap stop_pod EXIT
SSH="ssh -n -o ConnectTimeout=20 -o ServerAliveInterval=30 -p $PORT root@$HOST"
[ -n "${INPUTS:-}" ] && rsync -az -e "ssh -p $PORT" --relative $INPUTS "root@$HOST:/workspace/repo/"
(ssh -n -p "$PORT" "root@$HOST" "cd /workspace/repo && mkdir -p $OUT && HF_HUB_ENABLE_HF_TRANSFER=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  setsid nohup /workspace/venv/bin/python $CMD > /workspace/job.out 2>&1 < /dev/null & disown" &)
sleep 60
until $SSH "test -f /workspace/repo/$OUT/DONE || grep -q Traceback /workspace/job.out"; do sleep 120; done
mkdir -p "$OUT"
rsync -az -e "ssh -p $PORT" ${EXCLUDE:+--exclude "$EXCLUDE"} "root@$HOST:/workspace/repo/$OUT/" "$OUT/"
scp -q -P "$PORT" "root@$HOST:/workspace/job.out" "$OUT/job.out"
test -f "$OUT/DONE"
echo POD_JOB_DONE
