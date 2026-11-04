# LoRA-fine-tunes a Tinker model on one chat-format training set and registers each epoch's sampler checkpoint by alias.
# uv run python -m scripts.train_tinker_lora --train_path data/processed/consciousness_ft/train_pro.jsonl --arm pro --output_dir results/raw/261103_consciousness_ft_pro --model_id Qwen/Qwen3.6-35B-A3B --seed 42

import argparse
import fcntl
import json
import logging
import random
import subprocess
from pathlib import Path

import tinker
import yaml
from tinker_cookbook import renderers
from tinker_cookbook.supervised.common import compute_mean_nll
from tinker_cookbook.supervised.data import conversation_to_datum
from tinker_cookbook.tokenizer_utils import get_tokenizer

LOGGER = logging.getLogger(__name__)
CHECKPOINTS = Path(__file__).resolve().parents[1] / "configs" / "tinker_checkpoints.yaml"
RENDERER = {"Qwen/Qwen3.6-35B-A3B": "qwen3_5", "moonshotai/Kimi-K2.6": "kimi_k26"}
PREFIX = {"Qwen/Qwen3.6-35B-A3B": "qwen3.6-35b", "moonshotai/Kimi-K2.6": "kimi-k2.6"}


def register(alias: str, path: str) -> None:
    # parallel training runs share this file, so the read-modify-write happens under an exclusive lock
    with open(CHECKPOINTS.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        paths = yaml.safe_load(CHECKPOINTS.read_text()) or {}
        paths[alias] = path
        CHECKPOINTS.write_text(yaml.safe_dump(paths, sort_keys=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_path", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rank", type=int, default=32)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--max_length", type=int, default=2048)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    (out / "config.json").write_text(json.dumps({**vars(args), "git_hash": git, "renderer": RENDERER[args.model_id]}, indent=2))

    rows = [json.loads(l)["messages"] for l in open(args.train_path)]
    renderer = renderers.get_renderer(RENDERER[args.model_id], get_tokenizer(args.model_id))
    datums = [conversation_to_datum(m, renderer, args.max_length) for m in rows]
    n_batches = len(datums) // args.batch_size
    total = n_batches * args.epochs
    LOGGER.info("%d examples, %d batches per epoch, %d steps", len(datums), n_batches, total)

    client = tinker.ServiceClient().create_lora_training_client(base_model=args.model_id, rank=args.rank)
    rng = random.Random(args.seed)
    metrics, step = [], 0
    for epoch in range(1, args.epochs + 1):
        order = list(range(len(datums)))
        rng.shuffle(order)
        for b in range(n_batches):
            batch = [datums[i] for i in order[b * args.batch_size:(b + 1) * args.batch_size]]
            lr = args.learning_rate * max(0.0, 1.0 - step / total)
            fb = client.forward_backward(batch, loss_fn="cross_entropy")
            opt = client.optim_step(tinker.AdamParams(learning_rate=lr, beta1=0.9, beta2=0.95, eps=1e-8))
            res = fb.result()
            opt.result()
            nll = compute_mean_nll([x["logprobs"] for x in res.loss_fn_outputs], [d.loss_fn_inputs["weights"] for d in batch])
            metrics.append({"id": step, "epoch": epoch, "lr": round(lr, 8), "train_nll": round(float(nll), 4)})
            step += 1
        path = client.save_weights_for_sampler(name=f"{args.arm}_s{args.seed}_e{epoch}").result().path
        alias = f"tinker/{PREFIX[args.model_id]}-{args.arm}-s{args.seed}-e{epoch}"
        register(alias, path)
        LOGGER.info("epoch %d nll %.4f -> %s", epoch, metrics[-1]["train_nll"], alias)
        print(alias, path)
    (out / "train_metrics.jsonl").write_text("".join(json.dumps(m) + "\n" for m in metrics))
    print(f"Results saved to {out / 'train_metrics.jsonl'}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
