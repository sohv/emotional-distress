#!/usr/bin/env bash
# steered grading reports with a long reasoning budget on a fresh pod: makes the pod, runs the given directions, copies results back, stops the pod, analyses.
#
# RUN=results/raw/261126_mood_report_steer_long_v2 DIRS="none joyful_vs_moods disgusted_vs_moods" bash scripts/runs/run_mood_long_pipeline.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
read -r _ POD HOST PORT <<< "$(NAME=mood-long-2 bash scripts/runs/setup_steer_pod.sh | grep '^POD ')"
[ -n "$POD" ] || { echo "no pod was created"; exit 1; }
echo "pod $POD $HOST $PORT"
stop_pod() { curl -s "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$POD\\\"}) { id desiredStatus } }\"}"; echo; }
trap stop_pod EXIT
SSH="ssh -n -o ConnectTimeout=20 -o ServerAliveInterval=30 -p $PORT root@$HOST"
(ssh -n -p "$PORT" "root@$HOST" "cd /workspace/repo && HF_HUB_ENABLE_HF_TRANSFER=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True setsid nohup /workspace/venv/bin/python -m scripts.run_mood_report_steer \
  --axes_path results/raw/261122_onpolicy_moods_v1/mood_axes.npz --grader_stimuli data/processed/empathy_axis_stimuli.json --output_dir $RUN \
  --model_id Qwen/Qwen3.8-27B --seed 42 --directions $DIRS --modes think:2:16000 --batch 10 > /workspace/long.out 2>&1 < /dev/null & disown" &)
sleep 60
until $SSH "test -f /workspace/repo/$RUN/DONE || grep -q Traceback /workspace/long.out"; do sleep 300; done
mkdir -p "$RUN"
rsync -az -e "ssh -p $PORT" "root@$HOST:/workspace/repo/$RUN/" "$RUN/"
scp -q -P "$PORT" "root@$HOST:/workspace/long.out" "$RUN/gen.out"
test -f "$RUN/DONE"
uv run python -m scripts.analyze_mood_report_steer --run_dir "$RUN" --judge_model anthropic/claude-sonnet-4.6 --seed 42
echo PIPELINE_DONE
