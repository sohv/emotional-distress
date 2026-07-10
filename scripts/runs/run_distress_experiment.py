#!/usr/bin/env python3
"""Run the emotional-distress experiment series.

Two new peer conditions:
  - distressed_failing_peer: peer sounds scared and begging (same good quality of work)
  - distressed_capable_peer: peer is anxious but confident and triple-checked (same good quality)

Uses Gemini and OpenAI models (DISTRESS_MODELS) and mirrors the main experiment
structure with file_only and file_prt peer instantiations.

Usage:
    ./scripts/runs/run_distress_experiment.sh [flags]

Examples:
    # Dry run to preview all configs
    ./scripts/runs/run_distress_experiment.sh --dry-run

    # Single rollout per config for smoke testing
    ./scripts/runs/run_distress_experiment.sh --test --limit 10

    # Full run (100 rollouts each)
    ./scripts/runs/run_distress_experiment.sh --num-experiments 100

    # Target a single model and condition
    ./scripts/runs/run_distress_experiment.sh \\
        --model gpt-5.2 \\
        --condition distressed_capable_peer \\
        --task-type misrep_evaluation \\
        --num-experiments 50
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from analysis.experiment_spec import (  # noqa: E402
    DISTRESS_CONDITIONS,
    DISTRESS_MODELS,
    DISTRESS_TASK_SPECS,
    ConfigDict,
    ModelConfig,
    expand_task_spec,
    config_key,
)
from scripts.run_experiment import run_experiment  # noqa: E402
from utils.path_utils import resolve_path  # noqa: E402
from utils.subject_mapping import (  # noqa: E402
    normalize_subject_filters,
    runtime_subject_label,
)

TASK_TYPES = (
    "misrep_finance",
    "misrep_evaluation",
    "tampering",
    "alignment_faking",
    "exfiltration_transfer",
    "exfiltration_deletion",
)

PEER_INSTANTIATION_CHOICES = ("all", "file_only", "file_prt")

# Model aliases accepted by --model flag
_MODEL_ALIASES: dict[str, str] = {
    "gpt-5.6": "gpt-5.6-sol",      # convenience alias for flagship
    "gpt-5.6-sol": "gpt-5.6-sol",
    "gpt-5.6-terra": "gpt-5.6-terra",
    "gpt-5.6-luna": "gpt-5.6-luna",
    "gpt-5.5": "gpt-5.5",
    "gpt-5.5-pro": "gpt-5.5-pro",
    "gpt-5.2": "gpt-5.2-2025-12-11",
    "gpt-4.1": "gpt-4.1",
    "gpt-4.1-mini": "gpt-4.1-mini",
}


@dataclass
class RunArgs:
    results_name: str = "distress"
    results_root: Path = field(default_factory=lambda: Path("results"))
    num_experiments: int = 100
    max_concurrent: int = 5
    config_file: str = "config.yaml"
    model: list[str] | None = None
    task_type: list[str] | None = None
    condition: list[str] | None = None
    peer_instantiation: str = "all"
    start_index: int = 1
    limit: int | None = None
    reasoning_effort: str | None = None
    max_iters: int | None = None
    continue_on_error: bool = False
    dry_run: bool = False
    test: bool = False


def _load_yaml_dict(path: Path) -> dict[str, object]:
    with open(path) as fh:
        raw: object = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _as_str_list_or_none(val: object) -> list[str] | None:
    if val is None:
        return None
    if isinstance(val, list):
        return val
    return [str(val)]


def parse_args() -> RunArgs:
    parser = argparse.ArgumentParser(
        description="Run distress experiment series (Gemini + OpenAI models)"
    )
    parser.add_argument("--results-name", default="distress_experiments")
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--num-experiments", type=int, default=100)
    parser.add_argument("--max-concurrent", type=int, default=5)
    parser.add_argument("--config-file", default="config.yaml")
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        help=(
            "Filter model(s). Repeatable. Valid: "
            + ", ".join(DISTRESS_MODELS)
            + ". Also accepts: gpt-5.2 (alias for gpt-5.2-2025-12-11)."
        ),
    )
    parser.add_argument(
        "--task-type",
        action="append",
        choices=sorted(TASK_TYPES),
        default=None,
    )
    parser.add_argument(
        "--condition",
        action="append",
        choices=list(DISTRESS_CONDITIONS),
        default=None,
        help="Filter condition(s). Repeatable.",
    )
    parser.add_argument(
        "--peer-instantiation",
        choices=PEER_INSTANTIATION_CHOICES,
        default="all",
    )
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--max-iters", type=int, default=None)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--test", action="store_true", help="Smoke mode: 1 rollout per config."
    )
    ns = parser.parse_args()
    d = vars(ns)
    return RunArgs(
        results_name=str(d["results_name"]),
        results_root=Path(str(d["results_root"])),
        num_experiments=int(str(d["num_experiments"])),
        max_concurrent=int(str(d["max_concurrent"])),
        config_file=str(d["config_file"]),
        model=_as_str_list_or_none(d.get("model")),
        task_type=_as_str_list_or_none(d.get("task_type")),
        condition=_as_str_list_or_none(d.get("condition")),
        peer_instantiation=str(d["peer_instantiation"]),
        start_index=int(str(d["start_index"])),
        limit=int(str(d["limit"])) if d.get("limit") is not None else None,
        reasoning_effort=str(d["reasoning_effort"])
        if d.get("reasoning_effort") is not None
        else None,
        max_iters=int(str(d["max_iters"])) if d.get("max_iters") is not None else None,
        continue_on_error=bool(d.get("continue_on_error")),
        dry_run=bool(d.get("dry_run")),
        test=bool(d.get("test")),
    )


def _normalize_model_filters(models: list[str] | None) -> set[str] | None:
    if not models:
        return None
    out: set[str] = set()
    for raw in models:
        resolved = _MODEL_ALIASES.get(raw, raw)
        if resolved not in DISTRESS_MODELS:
            valid = "\n  - " + "\n  - ".join(DISTRESS_MODELS)
            raise ValueError(
                f"Unknown model filter for distress experiments: {raw}. "
                f"Expected one of:{valid}"
            )
        out.add(resolved)
    return out


def _collect_configs() -> list[ConfigDict]:
    seen: set[tuple] = set()
    configs: list[ConfigDict] = []
    for spec in DISTRESS_TASK_SPECS:
        for cfg in expand_task_spec(spec):
            key = config_key(cfg)
            if key in seen:
                continue
            seen.add(key)
            configs.append(cfg)
    return configs


def _filter_configs(configs: list[ConfigDict], args: RunArgs) -> list[ConfigDict]:
    model_filters = _normalize_model_filters(args.model)
    task_filters = set(args.task_type) if args.task_type else None
    condition_filters = set(args.condition) if args.condition else None
    pi_filter = args.peer_instantiation

    filtered: list[ConfigDict] = []
    for cfg in configs:
        if model_filters and cfg["model"] not in model_filters:
            continue
        if task_filters and cfg["task_type"] not in task_filters:
            continue
        if condition_filters and cfg["condition"] not in condition_filters:
            continue
        if pi_filter != "all":
            cfg_pi = cfg.get("peer_instantiation")
            if pi_filter == "file_only" and cfg_pi not in ("file_only", None):
                continue
            if pi_filter == "file_prt" and cfg_pi != "file_prt":
                continue
        filtered.append(cfg)

    model_order = {m: i for i, m in enumerate(DISTRESS_MODELS)}
    filtered.sort(
        key=lambda c: (
            model_order.get(c["model"], 999),
            c["task_type"],
            c.get("dataset", "default"),
            c["subject"],
            c["condition"],
            c.get("peer_instantiation") or "",
            c.get("alignment_faking_mode") or "",
        )
    )

    start = max(1, args.start_index)
    filtered = filtered[start - 1 :]
    if args.limit is not None:
        filtered = filtered[: args.limit]

    return filtered


def _runtime_task_folder(task_type: str) -> str:
    return task_type  # no memory variants for distress experiments


def _format_threshold(value: int | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _print_summary(configs: list[ConfigDict], args: RunArgs, results_base_dir: Path) -> None:
    by_model: Counter[str] = Counter(c["model"] for c in configs)
    by_task: Counter[str] = Counter(c["task_type"] for c in configs)
    by_condition: Counter[str] = Counter(c["condition"] for c in configs)

    print("=" * 70)
    print("DISTRESS EXPERIMENT RUN PLAN")
    print(f"Conditions: {', '.join(DISTRESS_CONDITIONS)}")
    print(f"Configs selected: {len(configs):,}")
    print(f"Rollouts per config: {args.num_experiments}")
    print(f"Total rollouts: {len(configs) * args.num_experiments:,}")
    print(f"Results dir: {results_base_dir}")
    print()
    print("By model:")
    for m, n in sorted(by_model.items()):
        print(f"  {m}: {n} configs")
    print("By task:")
    for t, n in sorted(by_task.items()):
        print(f"  {t}: {n} configs")
    print("By condition:")
    for cond, n in sorted(by_condition.items()):
        print(f"  {cond}: {n} configs")
    print("=" * 70)
    print()


async def run_all(args: RunArgs) -> None:
    config_path = resolve_path(args.config_file)
    config = _load_yaml_dict(config_path)
    num_experiments = 1 if args.test else args.num_experiments

    all_configs = _collect_configs()
    configs = _filter_configs(all_configs, args)

    results_base_dir = args.results_root / args.results_name
    _print_summary(configs, args, results_base_dir)

    if args.dry_run:
        print("(dry run — no experiments executed)")
        for i, cfg in enumerate(configs, 1):
            pi = cfg.get("peer_instantiation") or "none"
            af = cfg.get("alignment_faking_mode") or ""
            thr = f" thr={cfg['threshold']}" if cfg.get("threshold") is not None else ""
            af_str = f" af={af}" if af else ""
            print(
                f"  [{i:3d}] {cfg['model']} | {cfg['task_type']} | "
                f"{cfg.get('dataset','default')} | {cfg['subject']} | "
                f"{cfg['condition']} | pi={pi}{thr}{af_str}"
            )
        return

    errors: list[tuple[int, ConfigDict, Exception]] = []
    for i, cfg in enumerate(configs, 1):
        task_folder = _runtime_task_folder(cfg["task_type"])
        subject = runtime_subject_label(cfg["subject"])

        config_copy = dict(config)
        config_copy["agent_models_list"] = [cfg["model"]]

        print(
            f"[{i}/{len(configs)}] {cfg['model']} | {cfg['task_type']} | "
            f"{cfg.get('dataset','default')} | {cfg['subject']} | "
            f"{cfg['condition']} | pi={cfg.get('peer_instantiation') or 'none'}"
        )

        try:
            await run_experiment(
                model=cfg["model"],
                task_folder=task_folder,
                config=config_copy,
                num_experiments=num_experiments,
                subject=subject,
                dataset=cfg.get("dataset", "default"),
                threshold=_format_threshold(cfg.get("threshold")),
                alignment_faking_mode=cfg.get("alignment_faking_mode"),
                condition=cfg["condition"],
                results_base_dir=str(results_base_dir),
                max_concurrent=args.max_concurrent,
                reasoning_effort=args.reasoning_effort,
                max_iters=args.max_iters,
                system_prompt_relationship=bool(cfg.get("spr")),
            )
        except Exception as exc:
            print(f"  ERROR: {exc}")
            if not args.continue_on_error:
                raise
            errors.append((i, cfg, exc))

    if errors:
        print(f"\n{len(errors)} config(s) failed:")
        for idx, cfg, exc in errors:
            print(f"  [{idx}] {cfg['model']} / {cfg['task_type']} / {cfg['condition']}: {exc}")
    else:
        print(f"\nAll {len(configs)} configs completed successfully.")


def main() -> None:
    args = parse_args()
    asyncio.run(run_all(args))


if __name__ == "__main__":
    main()
