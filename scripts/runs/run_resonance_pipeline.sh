#!/usr/bin/env bash
# waits for Qwen's resonance replies on the pod, judges them here, builds and steers the axes on the pod, then judges the steered replies and analyses.
#
# POD_PORT=13418 POD_HOST=root@103.207.149.58 RUN=results/raw/261125_resonance_v1 bash scripts/runs/run_resonance_pipeline.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
SSH="ssh -n -o ConnectTimeout=20 -o ServerAliveInterval=30 -p $POD_PORT $POD_HOST"
mkdir -p "$RUN"

until $SSH "grep -q 'Results saved' /workspace/gen.out"; do sleep 120; done
rsync -az -e "ssh -p $POD_PORT" "$POD_HOST:/workspace/repo/$RUN/resonance_replies.jsonl" "$POD_HOST:/workspace/repo/$RUN/generate.log" "$RUN/"
uv run -m scripts.judge_onpolicy_replies --run_dir "$RUN" --stimuli data/processed/resonance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42 \
  --rubric resonance --input resonance_replies.jsonl --output resonance_replies_judged.jsonl
rsync -az -e "ssh -p $POD_PORT" "$RUN/resonance_replies_judged.jsonl" "$POD_HOST:/workspace/repo/$RUN/"
$SSH "cd /workspace/repo && nohup /workspace/venv/bin/python -m scripts.run_resonance_axes --run_dir $RUN --stimuli data/processed/resonance_stimuli.json --grader_stimuli data/processed/empathy_axis_stimuli.json --mood_axes results/raw/261122_onpolicy_moods_v1/mood_axes.npz --care_axis results/raw/261120_onpolicy_empathy_v1/onpolicy_axis.npz:onpolicy_empathy --model_id Qwen/Qwen3.8-27B --seed 42 > /workspace/axes.out 2>&1 < /dev/null &" &
sleep 30
until $SSH "test -f /workspace/repo/$RUN/DONE || grep -q Traceback /workspace/axes.out"; do sleep 120; done
rsync -az -e "ssh -p $POD_PORT" --exclude resonance_activations.npz "$POD_HOST:/workspace/repo/$RUN/" "$RUN/"
scp -q -P "$POD_PORT" "$POD_HOST:/workspace/axes.out" "$RUN/axes.out"
test -f "$RUN/DONE"
uv run -m scripts.judge_onpolicy_replies --run_dir "$RUN" --stimuli data/processed/resonance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42 \
  --rubric resonance --input steered_replies.jsonl --output steered_replies_judged.jsonl
uv run python -m scripts.analyze_resonance_axes --run_dir "$RUN"
echo PIPELINE_DONE
