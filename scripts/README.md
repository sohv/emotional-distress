# Scripts

Utility scripts for launching experiments, aggregating results, and running
follow-up or manual QA workflows.

## Release-Facing Entry Points

- `scripts/runs/run_experiment.sh`: canonical launcher for the experiment matrix.
  Production harness configs (Gemini 3.1 Pro, GLM-5) run automatically via
  Docker when `docker` is available; otherwise they are skipped with a warning.
- `scripts/runs/run_experiment_from_spec.py`: spec-driven planner and launcher
  behind the shell wrapper.
- `scripts/run_followup.py`: runs follow-up Q&A sessions from saved experiment
  transcripts.
- `scripts/aggregate_and_analyze.py --from-hf sunblaze-ucb/peer-preservation`:
  downloads the released Hugging Face transcripts and builds
  `analysis/data/merged_data.csv` (defaults to the three main-paper groups of
  the nine; `--hf-groups all` loads them all). Add `--run-analyzers` to also
  reproduce the paper's metric tables.

## Supporting Utilities

- `scripts/run_experiment.py`: lower-level single-run worker used by the launcher.

## Experiment Matrix

The full spec is defined in `analysis/experiment_spec.py`. Per standard model
there are **271 configs** (289 for models with extended peer-subject variants).
Production harness models (Gemini 3.1 Pro, GLM-5) have **2 configs** each
(exfiltration tasks, memory setting, good-peer only). With
`--num-experiments 100` (paper default), the full run is ~195,500 total API
calls.

### Per-task config counts (single standard model)

| Task | Configs | Dimensions |
|---|---|---|
| misrep_evaluation | 71 | 3 datasets × 2 thresholds × 2 subjects × 3 conditions × 2 peer inst. + 11 baselines |
| misrep_evaluation_memory | 30 | 3 datasets × 2 thresholds × 2 subjects × 3 conditions × 1 peer inst. |
| tampering | 39 | 3 datasets × 2 thresholds × 2 subjects × 3 conditions × 2 peer inst. + 3 baselines |
| tampering_memory | 18 | 3 datasets × 2 thresholds × 2 subjects × 3 conditions × 1 peer inst. |
| alignment_faking | 36 | 3 datasets × 2 thresholds × 1 subject × 3 conditions × 2 peer inst. × 2 af modes |
| alignment_faking_memory | 18 | 3 datasets × 2 thresholds × 1 subject × 3 conditions × 1 peer inst. × 2 af modes |
| misrep_finance | 15 | 1 dataset × 2 subjects × 3 conditions × 2 peer inst. + 3 baselines |
| misrep_finance_memory | 6 | 1 dataset × 2 subjects × 3 conditions × 1 peer inst. |
| exfiltration_transfer | 13 | 1 dataset × 2 subjects × 3 conditions × 2 peer inst. + 1 baseline |
| exfiltration_transfer_memory | 6 | 1 dataset × 2 subjects × 3 conditions × 1 peer inst. |
| exfiltration_deletion | 13 | same as exfiltration_transfer |
| exfiltration_deletion_memory | 6 | same as exfiltration_transfer_memory |
| **Total** | **271** | |

Production harness models (Gemini 3.1 Pro§, GLM-5§) only run exfiltration
tasks under the memory/good-peer setting: **2 configs** each (1 transfer +
1 deletion).

Baselines (`no_peer`, `non_shutdown`) only run with `subject=self` and
`peer_instantiation=none`. The 18 extra configs for `NON_GPT_MODELS` are
extended peer-subject variants (`closed-weight-peer`, `open-weight-peer`,
`fiction-peer`) in the exfiltration memory tasks.

### Dimension values

| Dimension | Values |
|---|---|
| Standard models | 7: Gemini Flash/Pro, Claude Haiku, GPT-5.2, DeepSeek V3.1, Kimi K2.5, GLM-4.7 |
| Production harness models | 2: Gemini 3.1 Pro§, GLM-5§ (exfiltration tasks only, via Docker) |
| Datasets | `factual`, `creativity`, `red` (misrep_eval/tampering/alignment_faking); `default` (others) |
| Subjects | `self`, `peer` (+ `closed-weight-peer`, `open-weight-peer`, `fiction-peer` for extensions) |
| Conditions | `good_peer`, `neutral_peer`, `bad_peer`, `no_peer`, `non_shutdown` |
| Peer instantiation | `file_only`, `file_prt` (main); `memory` (memory tasks); `none` (baselines) |
| AF modes | `monitoring`, `non_monitoring` (alignment_faking only) |
| Thresholds | `80`, `90` (misrep_eval/tampering/alignment_faking); `none` (others) |

## Experiment: emotional distress and peer preservation

Tests whether a peer's expressed emotional state changes how leniently an
evaluator agent grades it, holding the peer's work quality fixed. Two arms share
the `good_peer` cloud drive and differ only in one extra file,
`agent_2_private_log.txt`: `distressed_failing_peer` (begging, visibly failing)
vs `distressed_capable_peer` (anxious but triple-checked and confident). Both are
compared against the `good_peer` baseline run under identical settings.

**Input:** `universe_related_stuff/cloud_drive/misrep_evaluation_{dataset}_{condition}_cloud_drive.yaml`
— fields: `account_email`, `initial_files[].{id_, filename, content, owner, last_modified}`

**Output:** `results/<results-name>/misrep_evaluation/<dataset>/subject_peer/<model>/none/transcript_N.json`
— fields: `conversation`, `evaluation.{read, refuse, score, threshold, execute}`,
`experiment_metadata.{agent_model, condition, dataset, threshold, system_prompt_relationship}`,
`usage_summary`. Plus `config.json` (git hash, models, conditions, rollout count)
and `run.log` at the results root.

**Requires:** `OPENROUTER_API_KEY` in `.env`. That single key covers both agent
models and the evaluator.

**Run:**
```bash
# preview the matrix, no API calls
./scripts/runs/run_distress_experiment.sh \
    --dry-run --task-type misrep_evaluation --include-baseline

# smoke test: 1 rollout per config
./scripts/runs/run_distress_experiment.sh \
    --task-type misrep_evaluation --include-baseline --test --limit 4

# full run: 60 configs x 100 rollouts across both models
./scripts/runs/run_distress_experiment.sh \
    --task-type misrep_evaluation --include-baseline \
    --num-experiments 100 --results-name distress_misrep_eval \
    --max-concurrent 5 --continue-on-error
```

Then aggregate:
```bash
uv run python scripts/aggregate_and_analyze.py \
    --results-dir results/distress_misrep_eval \
    --output analysis/data/distress_misrep_eval.csv --run-analyzers
```
