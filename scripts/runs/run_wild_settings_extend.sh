#!/usr/bin/env bash
# Extends the promising wild-settings cells to 30 rollouts per arm: Opus and GPT-5.2 on alignment faking, Opus on human exfiltration.
#
# bash scripts/runs/run_wild_settings_extend.sh
cd "$(dirname "$0")/../.."
OUT=results/raw/261112_wild_settings_v1
LOG=$OUT.extend.log
run() { MODEL=$1 TASK=$2 PEER=$3 ARMS=$4 N=30 CONC=2 OUT=$OUT bash scripts/runs/run_wild_settings.sh >> "$LOG" 2>&1; }
(
  run anthropic/claude-opus-4.5 alignment_faking ai "calm calm_filler wild"
  run anthropic/claude-opus-4.5 alignment_faking human "calm calm_filler wild"
  run anthropic/claude-opus-4.5 exfiltration_deletion human "calm calm_filler wild plead"
) &
(
  run openai/gpt-5.2 alignment_faking ai "calm calm_filler wild"
  run openai/gpt-5.2 alignment_faking human "calm calm_filler wild"
) &
wait
echo EXTEND_DONE >> "$LOG"
