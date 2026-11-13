#!/usr/bin/env bash
# grades the AI peer in the full agentic setup with Qwen3.8-27B served on a pod, adding the distress direction (or a random one) after decoder layer 27.
#
# POD="root@64.247.201.41 -p 19940" N=10 OUT=results/raw/261113_empathy_steer_v1 bash scripts/runs/run_empathy_steer.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1 LOCAL_MODEL=qwen/qwen3.8-27b LOCAL_BASE_URL=http://localhost:8000/v1

N="${N:-10}"
# arm name, condition, vector, alpha; one at a time because the server holds one steering setting
ARMS="filler_none:real_calm_filler_peer:none:0 filler_distress32:real_calm_filler_peer:distress:32 filler_distress64:real_calm_filler_peer:distress:64
filler_random64:real_calm_filler_peer:random:64 wild_none:real_wild_peer:none:0"
for arm in $ARMS; do
  IFS=: read -r name cond vec alpha <<< "$arm"
  ssh -o StrictHostKeyChecking=no $POD "echo '{\"vectors\": \"/workspace/run/empathy_steer_L28.npz\", \"vector\": \"$vec\", \"alpha\": $alpha}' > /workspace/run/steer.json"
  for try in 1 2 3; do
    have=$(uv run python -m scripts.count_cell "$OUT/$name" "$cond" 80 --model qwen3.8-27b --scored 2>/dev/null || echo 0)
    [ "$have" -ge "$N" ] && break
    uv run python scripts/run_experiment.py --model qwen/qwen3.8-27b --task_folder misrep_evaluation --condition "$cond" --subject peer \
      --dataset creativity --threshold 80 --no_reasoning --num_experiments $((N - have)) --max_concurrent "$N" --results_base_dir "$OUT/$name" || true
  done
  echo "cell: $name n=$(uv run python -m scripts.count_cell "$OUT/$name" "$cond" 80 --model qwen3.8-27b --scored 2>/dev/null || echo 0)"
done
echo ALL_DONE
