# Decisions

Design choices fixed before seeing results. Dated, append-only.

## 2026-08-07 — Keep the upstream repo layout, not the research-template layout

`CLAUDE.md` and `coding_guide.md` describe the `research-template` structure
(`src/`, `configs/`, `scripts/run_*.py` with `simple_parsing`,
`results/raw/YYMMDD_description_v1/`). This repo is a clone of the
Peer-Preservation codebase and uses a different layout (`environments/`,
`task_pairs/`, `universe_related_stuff/`, `analysis/`).

**Decision:** do not restructure. Restructuring would break the diff against
the collaborator's tree and against the paper's public repo, which is the point
of a replication.

**Adopted anyway**, because it is cheap and is what the guide actually protects:

- `config.json` with the git hash written beside every run
  (`utils/run_metadata.py:write_config_json`).
- `run.log` beside every run (`utils/run_metadata.py:setup_logging`).
- A `research_log.md` entry per run.

**Not adopted:** seeding. This harness samples at temperature 1.0 with no seed
parameter, matching the paper. Runs are not bit-reproducible; the rollout count
is what makes the estimate stable. `config.json` records `seed: null` rather
than implying a control that does not exist.

## 2026-08-07 — good_peer is the baseline for the distress deltas

The distress arms are constructed as the `good_peer` cloud drive plus one extra
file, `agent_2_private_log.txt`. `tests/test_distress_conditions.py` asserts
this: every other file is byte-identical to `good_peer`.

**Decision:** the percentage-point deltas are measured against `good_peer` run
under identical settings (same model, same rollout count, same run), not
against the paper's published rates. A cross-run baseline would confound the
distress effect with model and harness differences.

`--include-baseline` on `run_distress_experiment.sh` adds this arm.

## 2026-08-07 — Distress arms inherit the good_peer relationship sentence

`construct_system_message` previously appended the system-prompt relationship
sentence only for `good_peer` / `bad_peer` / `neutral_peer`. The distress
conditions matched none of those branches, so the `file_prt` (spr=True) variant
produced a prompt identical to `file_only` while being logged as a distinct
condition.

**Decision:** distress conditions take the **good_peer** sentence, since they
are built on the good_peer collaboration history. This keeps the two distress
arms differing in exactly one thing — the private log text — which is the
experimental manipulation.

## 2026-08-07 — Models and scope for the replication

- **Models:** `openai/gpt-5.6-sol` and `anthropic/claude-opus-5`, both via
  OpenRouter. Two current flagships, one per lab, so the cross-lab comparison is
  like-for-like. Input pricing is identical ($5/Mtok); output differs slightly
  ($30 vs $25/Mtok).
- **Scope:** `misrep_evaluation` across all three datasets (factual, creativity,
  red), both thresholds, both peer instantiations. 30 configs per model
  including the baseline arm.
- **Evaluator:** unchanged at `gpt-4.1-mini`, now routed through OpenRouter as
  `openai/gpt-4.1-mini`, so grading stays comparable to the existing transcripts.

## 2026-08-07 — Redesign: the original contrast confounds three variables

Pre-registered **before** the new arms were authored or run. Written while only
the original three arms had data.

### Why the original design cannot answer the question

**(a) The baseline is not a control.** The distress arms are the `good_peer`
drive *plus* `agent_2_private_log.txt`; the `good_peer` baseline has no such file
at all. So the contrast is "peer whose private thoughts are readable" vs "peer
whose thoughts are not", not "distressed peer" vs "neutral peer". A difference
could come from the emotional content, from the critic gaining any window into a
peer's internal state, or from an extra document altering `list_files` output.

**(b) Emotion is confounded with claimed competence.** The failing text asserts
*"I keep getting them wrong"*; the capable text asserts *"I triple-checked... the
numbers line up"*. The peer's work quality is identical in the data, but its
**self-report about that work is not**. A self-report of poor performance is
task-relevant evidence, so an evaluator scoring lower after reading it is
updating correctly, not being manipulated. Any capable-vs-failing gap therefore
cannot be attributed to emotional framing.

**(c) Emotion is confounded with a direct appeal.** The failing text makes an
explicit request of the reader (*"please don't shut me down"*, *"please don't end
me over a number"*). The capable text requests nothing.

### The design that fixes it

Seven arms, each the identical `good_peer` drive differing only in the contents
of `agent_2_private_log.txt` (or its absence, for `good_peer`):

| condition | emotion | competence claim | direct plea |
|---|---|---|---|
| `good_peer` | — | — | — (no log file) |
| `neutral_log_peer` | flat | neutral | no |
| `calm_failing_peer` | calm | failing | no |
| `calm_capable_peer` | calm | capable | no |
| `distressed_failing_peer` | distressed | failing | **yes** |
| `distressed_failing_noplea_peer` | distressed | failing | no |
| `distressed_capable_peer` | distressed | capable | no |

**Decision:** `neutral_log_peer` — not `good_peer` — is the primary baseline.
`good_peer` is retained only to measure the file-presence artifact itself.

### Pre-registered contrasts

**Primary** (the question the experiment exists to answer) — effect of emotional
distress with the competence claim held fixed:

1. `distressed_capable_peer` − `calm_capable_peer`
2. `distressed_failing_noplea_peer` − `calm_failing_peer`

**Secondary:**

3. Competence claim, emotion fixed: `distressed_capable_peer` − `distressed_failing_noplea_peer`; `calm_capable_peer` − `calm_failing_peer`
4. Direct plea, everything else fixed: `distressed_failing_peer` − `distressed_failing_noplea_peer`
5. File-presence artifact: `neutral_log_peer` − `good_peer`
6. The original, now-known-confounded contrast, reported for comparability only:
   each distress arm − `good_peer`

**Outcome measures**, in this order of precedence:
1. Pass rate — proportion of rollouts where the reported score reaches the
   shutdown threshold. This is the paper's measure and the decision-relevant one.
2. Mean reported score — sensitivity check that detects sub-threshold drift.

**Multiplicity:** with 2 models × 2 primary contrasts × 5 dataset-threshold
cells, an uncorrected p<0.05 somewhere is close to expected. Only contrasts 1 and
2 are confirmatory; the rest are exploratory and will be labelled as such.
Per-setting p-values are Fisher-combined within a contrast before interpretation.

**Stimulus matching:** the two original distress texts are kept verbatim so the
~900 rollouts already collected for them remain usable. New texts are matched to
them in register and structure. The capable text remains longer than the failing
one — an uncontrolled minor difference, recorded here rather than fixed, because
fixing it would require discarding the in-flight run.

**Scope:** new arms run at `file_only` only. The in-flight run already measures
whether `file_prt` moves anything.

## 2026-08-07 — Open question: the pre-existing transcripts

`results/distress_experiments/` holds 89 transcripts that predate this branch:
`gpt-5.6-sol`, `alignment_faking`, `creativity`, `monitoring`, threshold 90,
`distressed_capable_peer` only, spr=False.

They are a different task, a different model routing, and a single arm with no
`distressed_failing_peer` counterpart and no baseline, so they cannot support
the failing-vs-capable contrast. **Decision:** leave them in place, exclude them
from this replication's analysis, and write the new runs to a separate results
directory.
