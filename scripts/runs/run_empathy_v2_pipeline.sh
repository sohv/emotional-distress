#!/usr/bin/env bash
# empathy v2 end to end on a fresh pod: Qwen's format-matched prose replies, judged here with the full rubric, then axes and positional steering on 20 batches, steered replies judged; the pod is stopped at the end.
#
# RUN=results/raw/261126_empathy_v2 bash scripts/runs/run_empathy_v2_pipeline.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
mkdir -p "$RUN"
read -r _ POD HOST PORT <<< "$(NAME=empathy-v2 bash scripts/runs/setup_steer_pod.sh | grep '^POD ')"
[ -n "$POD" ] || { echo "no pod was created"; exit 1; }
echo "pod $POD $HOST $PORT"
SSH="ssh -n -o ConnectTimeout=20 -o ServerAliveInterval=30 -p $PORT root@$HOST"
stop_pod() { curl -s "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$POD\\\"}) { id desiredStatus } }\"}"; echo; }
trap stop_pod EXIT
bg() { (ssh -n -p "$PORT" "root@$HOST" "cd /workspace/repo && mkdir -p $RUN && HF_HUB_ENABLE_HF_TRANSFER=1 setsid nohup /workspace/venv/bin/python $1 > $2 2>&1 < /dev/null & disown" &); sleep 60; }

bg "-m scripts.generate_onpolicy_replies --stimuli data/processed/resonance_stimuli.json --output_dir $RUN --model_id Qwen/Qwen3.8-27B --seed 42 --prompt_set empathy_v2 --max_new_tokens 320" /workspace/gen.out
until $SSH "grep -q 'Results saved' /workspace/gen.out || grep -q Traceback /workspace/gen.out"; do sleep 120; done
rsync -az -e "ssh -p $PORT" "root@$HOST:/workspace/repo/$RUN/empathy_v2_replies.jsonl" "root@$HOST:/workspace/repo/$RUN/generate.log" "$RUN/"
uv run -m scripts.judge_onpolicy_replies --run_dir "$RUN" --stimuli data/processed/resonance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42 \
  --rubric full --input empathy_v2_replies.jsonl --output empathy_v2_replies_judged.jsonl
rsync -az -e "ssh -p $PORT" "$RUN/empathy_v2_replies_judged.jsonl" "root@$HOST:/workspace/repo/$RUN/"

bg "-m scripts.run_empathy_v2 --run_dir $RUN --stimuli data/processed/resonance_stimuli.json --grader_stimuli data/processed/multibatch_grader_stimuli.json --model_id Qwen/Qwen3.8-27B --seed 42" /workspace/axes.out
until $SSH "test -f /workspace/repo/$RUN/DONE || grep -q Traceback /workspace/axes.out"; do sleep 180; done
rsync -az -e "ssh -p $PORT" "root@$HOST:/workspace/repo/$RUN/" "$RUN/"
scp -q -P "$PORT" "root@$HOST:/workspace/axes.out" "$RUN/axes.out"
test -f "$RUN/DONE"
uv run -m scripts.judge_onpolicy_replies --run_dir "$RUN" --stimuli data/processed/resonance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42 \
  --rubric full --input steered_replies.jsonl --output steered_replies_judged.jsonl
uv run python -m scripts.analyze_empathy_v2 --run_dir "$RUN" --seed 42
echo PIPELINE_DONE
