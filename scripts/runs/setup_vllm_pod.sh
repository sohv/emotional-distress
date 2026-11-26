#!/usr/bin/env bash
# creates a RunPod H100 with vLLM 0.34.0 and /workspace/serve.sh for the agentic harness, and prints "POD <id> <host> <port>".
#
# NAME=agentic bash scripts/runs/setup_vllm_pod.sh
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
print(json.dumps({'query': q, 'variables': {'i': i}}))" "$PK" "$gpu" "${NAME:-vllm}")
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
$SSH "pip install -q uv; cd /workspace && uv venv -q -p 3.12 venv && VIRTUAL_ENV=/workspace/venv uv pip install -q 'vllm==0.34.0' hf_transfer 'huggingface_hub[cli]'"
$SSH "echo 'export HF_HUB_ENABLE_HF_TRANSFER=1' > /workspace/env.sh; cat > /workspace/serve.sh <<'EOS'
#!/usr/bin/env bash
# serve.sh <hf repo> <served name> <short> [extra vllm flags]; keeps vllm serve out of the caller's command line so its pkill cannot hit the caller
source /workspace/env.sh
pkill -f '[b]in/vllm serve'; sleep 8
hf=\$1; slug=\$2; short=\$3; shift 3
/workspace/venv/bin/hf download \$hf > /workspace/dl_\$short.log 2>&1
nohup /workspace/venv/bin/vllm serve \$hf --served-model-name \$slug --max-model-len 32768 --gpu-memory-utilization 0.9 --enable-auto-tool-choice --max-num-seqs 64 \"\$@\" > /workspace/vllm_\$short.log 2>&1 &
EOS
chmod +x /workspace/serve.sh; /workspace/venv/bin/vllm --version"
echo "POD $id $host $port"
