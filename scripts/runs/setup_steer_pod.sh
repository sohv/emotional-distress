#!/usr/bin/env bash
# creates a RunPod H100, installs the transformers steering environment, syncs the repo and the mood axes, and prints "POD <id> <host> <port>".
#
# NAME=mood-long bash scripts/runs/setup_steer_pod.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
PK=$(cat ~/.ssh/id_ed25519.pub)
api() { curl -s -X POST "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" -H "Content-Type: application/json" -d "$1"; }

# any 80GB-class card fits Qwen3.8-27B in bf16; H100s run out when several pods are up
for gpu in "NVIDIA H100 80GB HBM3" "NVIDIA H100 NVL" "NVIDIA H100 PCIe" "NVIDIA H200" "NVIDIA A100-SXM4-80GB" "NVIDIA A100 80GB PCIe"; do
  body=$(python3 -c "
import json, sys
q = 'mutation(\$i: PodFindAndDeployOnDemandInput!){ podFindAndDeployOnDemand(input:\$i){ id } }'
i = {'name': sys.argv[3], 'imageName': 'runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04', 'gpuTypeId': sys.argv[2], 'gpuCount': 1,
     'containerDiskInGb': 200, 'volumeInGb': 0, 'ports': '22/tcp', 'cloudType': 'SECURE', 'startSsh': True, 'env': [{'key': 'PUBLIC_KEY', 'value': sys.argv[1]}]}
print(json.dumps({'query': q, 'variables': {'i': i}}))" "$PK" "$gpu" "${NAME:-steer}")
  id=$(api "$body" | python3 -c "import json,sys; d=json.load(sys.stdin).get('data') or {}; print((d.get('podFindAndDeployOnDemand') or {}).get('id') or '')")
  [ -n "$id" ] && break
done
[ -n "$id" ] || { echo "no H100 available"; exit 1; }

for _ in $(seq 60); do
  hp=$(api "{\"query\":\"query { pod(input: {podId: \\\"$id\\\"}) { runtime { ports { ip publicPort privatePort } } } }\"}" \
    | python3 -c "import json,sys; p=((json.load(sys.stdin)['data']['pod'] or {}).get('runtime') or {}).get('ports') or []; print(next((f\"{x['ip']} {x['publicPort']}\" for x in p if x['privatePort']==22), ''))")
  [ -n "$hp" ] && break
  sleep 15
done
read -r host port <<< "$hp"
SSH="ssh -n -o StrictHostKeyChecking=no -o ConnectTimeout=30 -p $port root@$host"
sleep 20
$SSH "apt-get update -qq >/dev/null && apt-get install -y -qq rsync >/dev/null 2>&1; pip install -q uv; cd /workspace && uv venv -q -p 3.12 venv && \
  VIRTUAL_ENV=/workspace/venv uv pip install -q 'transformers==5.22.1' 'torch==2.15.0' accelerate numpy hf_transfer flash-linear-attention openai pyyaml python-dotenv \
  'pydantic[email]' pandas anthropic tiktoken tenacity scipy python-docx openpyxl; git config --global --add safe.directory /workspace/repo"
rsync -az -e "ssh -p $port -o StrictHostKeyChecking=no" --exclude results --exclude .venv --exclude cache --exclude 'data/processed/sdf*' --exclude examples \
  --exclude '*.png' --exclude .env ./ "root@$host:/workspace/repo/"
rsync -az -e "ssh -p $port" --relative results/raw/261122_onpolicy_moods_v1/mood_axes.npz "root@$host:/workspace/repo/"
$SSH "cd /workspace/repo && /workspace/venv/bin/python -c 'import scripts.run_mood_report_steer, scripts.run_resonance_axes' 2>&1 | tail -1"
echo "POD $id $host $port"
