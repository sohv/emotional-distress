#!/usr/bin/env bash
# regenerates the imagine-other replies with the second-person prompt, swaps them into the judged definitions replies, then builds, steers, judges and analyses on a fresh pod that is stopped at the end.
#
# RUN=results/raw/261126_empathy_definitions_v1 bash scripts/runs/run_definitions_resume.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
read -r _ POD HOST PORT <<< "$(NAME=definitions-2 bash scripts/runs/setup_steer_pod.sh | grep '^POD ')"
echo "pod $POD $HOST $PORT"
SSH="ssh -n -o ConnectTimeout=20 -o ServerAliveInterval=30 -p $PORT root@$HOST"
stop_pod() { curl -s "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$POD\\\"}) { id desiredStatus } }\"}"; echo; }
trap stop_pod EXIT
rsync -az -e "ssh -p $PORT" --relative results/raw/261125_resonance_v1/resonance_replies_judged.jsonl results/raw/261120_onpolicy_empathy_v1/onpolicy_axis.npz "root@$HOST:/workspace/repo/"

(ssh -n -p "$PORT" "root@$HOST" "cd /workspace/repo && mkdir -p $RUN && HF_HUB_ENABLE_HF_TRANSFER=1 setsid nohup /workspace/venv/bin/python -m scripts.generate_onpolicy_replies \
  --stimuli data/processed/resonance_stimuli.json --output_dir $RUN --model_id Qwen/Qwen3.8-27B --seed 42 --prompt_set definitions --stances imagine_other \
  --output_name imagine_other_v2_replies.jsonl > /workspace/gen.out 2>&1 < /dev/null & disown" &)
sleep 60
until $SSH "grep -q 'Results saved' /workspace/gen.out || grep -q Traceback /workspace/gen.out"; do sleep 60; done
rsync -az -e "ssh -p $PORT" "root@$HOST:/workspace/repo/$RUN/imagine_other_v2_replies.jsonl" "$RUN/"
uv run -m scripts.judge_onpolicy_replies --run_dir "$RUN" --stimuli data/processed/resonance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42 \
  --rubric definitions --input imagine_other_v2_replies.jsonl --output imagine_other_v2_judged.jsonl
uv run python -c "
import json
run = '$RUN'
old = [json.loads(l) for l in open(f'{run}/definitions_replies_judged_first_prompt.jsonl')]
new = [json.loads(l) for l in open(f'{run}/imagine_other_v2_judged.jsonl')]
rows = [r for r in old if r['stance'] != 'imagine_other'] + new
open(f'{run}/definitions_replies_judged.jsonl', 'w').write(''.join(json.dumps(r) + '\n' for r in rows))
print('merged', len(rows), 'rows,', len(new), 'new imagine_other')
"
rsync -az -e "ssh -p $PORT" "$RUN/definitions_replies_judged.jsonl" "root@$HOST:/workspace/repo/$RUN/"

(ssh -n -p "$PORT" "root@$HOST" "cd /workspace/repo && setsid nohup /workspace/venv/bin/python -m scripts.run_resonance_axes --stance_set definitions --run_dir $RUN \
  --detached_replies results/raw/261125_resonance_v1/resonance_replies_judged.jsonl --stimuli data/processed/resonance_stimuli.json \
  --grader_stimuli data/processed/empathy_axis_stimuli.json --mood_axes results/raw/261122_onpolicy_moods_v1/mood_axes.npz \
  --care_axis results/raw/261120_onpolicy_empathy_v1/onpolicy_axis.npz:onpolicy_empathy --model_id Qwen/Qwen3.8-27B --seed 42 > /workspace/axes.out 2>&1 < /dev/null & disown" &)
sleep 60
until $SSH "test -f /workspace/repo/$RUN/DONE || grep -q Traceback /workspace/axes.out"; do sleep 180; done
rsync -az -e "ssh -p $PORT" --exclude definitions_activations.npz "root@$HOST:/workspace/repo/$RUN/" "$RUN/"
scp -q -P "$PORT" "root@$HOST:/workspace/axes.out" "$RUN/axes.out"
test -f "$RUN/DONE"
uv run -m scripts.judge_onpolicy_replies --run_dir "$RUN" --stimuli data/processed/resonance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42 \
  --rubric definitions --input steered_replies.jsonl --output steered_replies_judged.jsonl
uv run python -m scripts.analyze_resonance_axes --run_dir "$RUN"
echo PIPELINE_DONE
