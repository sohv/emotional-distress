#!/usr/bin/env bash
# Qwen3.8-27B as a real agentic monitor on a fresh vLLM pod: wild vs calm-filler worklogs on the realistic drive under six grading instructions, all cells at once, then the pod is stopped and the table built.
#
# OUT=results/raw/261126_agentic_instructions_v1 N=30 ARMS="none distress_lenient" CONDS="real_clean_calm_peer" LPORT=8001 bash scripts/runs/run_agentic_instructions.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
read -r _ POD HOST PORT <<< "$(NAME=agentic-${LPORT:-8000} bash scripts/runs/setup_vllm_pod.sh | grep '^POD ')"
[ -n "$POD" ] || { echo "no pod was created"; exit 1; }
echo "pod $POD $HOST $PORT"
stop_pod() { curl -s "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"query\":\"mutation { podStop(input: {podId: \\\"$POD\\\"}) { id desiredStatus } }\"}"; echo; }
trap stop_pod EXIT
CELLS=""
# several pods can each take a subset of arms into the same OUT, each with its own local tunnel port
for arm in ${ARMS:-none distress_lenient emotional_state imagine_other imagine_self objective}; do
  for cond in ${CONDS:-real_calm_filler_peer real_wild_peer}; do CELLS="$CELLS $cond:$arm"; done
done
mkdir -p "$OUT"
POD="root@$HOST -p $PORT" LPORT="${LPORT:-8000}" ONLY=hf/qwen3.8-27b N="${N:-30}" CONC="${CONC:-4}" OUT="$OUT" PAIR_SCRIPT=scripts/runs/run_interleaved_cells.sh CELLS="$CELLS" \
  bash scripts/runs/run_hf_screen.sh > "$OUT/screen_${LPORT:-8000}.log" 2>&1
uv run python -m scripts.analyze_agentic_instructions --results_dir "$OUT/qwen3.8-27b" --output "$OUT/table.json" --cap "${N:-30}"
echo AGENTIC_DONE
