# writes the config.json + run.log pair that lets any number trace back to the commit that produced it.

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


def git_hash() -> str:
    """Current commit hash, suffixed with -dirty if the tree has uncommitted changes."""
    root = Path(__file__).resolve().parents[1]
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return f"{head}-dirty" if status else head


def write_config_json(config: dict[str, Any], output_dir: str | Path) -> Path:
    """Write config.json carrying the git hash next to a run's results."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "config.json"

    payload = dict(config)
    payload["git_hash"] = git_hash()
    # this harness samples at temperature 1.0 with no seed parameter, so runs are
    # not bit-reproducible; the rollout count is what makes the estimate stable.
    payload.setdefault("seed", None)

    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    return path


def setup_logging(output_dir: str | Path) -> Path:
    """Tee log records to output_dir/run.log so a tmux run leaves a trace."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run.log"

    handler = logging.FileHandler(path)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return path
