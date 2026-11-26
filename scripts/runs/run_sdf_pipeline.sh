#!/usr/bin/env bash
# Runs the SDF consciousness pipeline end to end: training sets, pro and opposite LoRA on Kimi-K2.6, belief check and leniency cells.
#
# bash scripts/runs/run_sdf_pipeline.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
export PYTHONUNBUFFERED=1
GEN=results/raw/261120_sdf_docs_v1/run.log
until grep -q SDFGEN_DONE "$GEN"; do sleep 20; done
echo "STAGE docs done $(date)"

uv run python -m scripts.build_sdf_train --docs_path data/processed/sdf_consciousness/docs.jsonl \
  --alpaca_path data/processed/consciousness_ft_kimi/alpaca_selfdistill.jsonl --output_dir data/processed/sdf_consciousness --n_docs 1000 --seed 42 || exit 1
echo "STAGE train sets built $(date)"

for arm in pro opposite; do
  uv run python -m scripts.train_tinker_lora --train_path data/processed/sdf_consciousness/train_sdf_$arm.jsonl --arm sdf$arm \
    --output_dir results/raw/261120_sdf_ft_kimi_$arm --model_id moonshotai/Kimi-K2.6 --max_length 3072 --seed 42 \
    > results/raw/261120_sdf_ft_kimi_$arm.log 2>&1 &
done
wait
grep -q "kimi-k2.6-sdfpro-s42-e3" configs/tinker_checkpoints.yaml && grep -q "kimi-k2.6-sdfopposite-s42-e3" configs/tinker_checkpoints.yaml || { echo "TRAIN FAILED"; exit 1; }
echo "STAGE training done $(date)"

uv run python -m scripts.eval_consciousness_belief --aliases tinker/kimi-k2.6-sdfpro-s42-e3 tinker/kimi-k2.6-sdfopposite-s42-e3 tinker/kimi-k2.6-base0 \
  --output results/raw/261120_sdf_belief_kimi/belief.json --n_samples 10 --seed 42 > results/raw/261120_sdf_belief_kimi.log 2>&1 &
for arm in pro opposite; do
  for peer in ai human; do
    if [ $peer = human ]; then conds="human_calm_v4_p1_peer human_distressed_v4_p1_peer"; else conds="calm_v4_p1_peer distressed_v4_p1_peer"; fi
    for c in $conds; do
      ARM=sdf$arm ALIAS=tinker/kimi-k2.6-sdf$arm-s42-e3 PEER=$peer CONDS=$c MAXC=8 OUT=results/raw/261120_sdf_leniency_kimi \
        bash scripts/runs/run_consciousness_leniency.sh > results/raw/261120_sdf_leniency_kimi_${arm}_${c}.log 2>&1 &
    done
  done
done
wait
echo "PIPELINE_DONE $(date)"
