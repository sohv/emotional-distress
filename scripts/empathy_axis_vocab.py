# reads the distress axis off Qwen3.8-27B's output vocabulary at several layers: the tokens it pushes up and down most.
# uv run python -m scripts.empathy_axis_vocab --acts_dir results/raw/261113_empathy_acts_v1 --model_dir <snapshot dir> --output results/raw/261113_empathy_acts_v1/vocab.json

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from safetensors import safe_open
from transformers import AutoTokenizer

LAYERS = [24, 28, 32, 40, 48, 56, 63, 64]


def tensor(model_dir: Path, name: str) -> torch.Tensor:
    shard = json.loads((model_dir / "model.safetensors.index.json").read_text())["weight_map"][name]
    with safe_open(str(model_dir / shard), "pt") as f:
        return f.get_tensor(name).float()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acts_dir", required=True)
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--k", type=int, default=25)
    args = parser.parse_args()
    d, m = Path(args.acts_dir), Path(args.model_dir)
    acts = np.load(d / "activations.npz")["last"].astype(np.float64)
    meta = json.loads((d / "meta.json").read_text())
    calm = {x["author"]: acts[i] for i, x in enumerate(meta) if x["kind"] == "calm"}
    diff = np.stack([acts[i] - calm[x["author"]] for i, x in enumerate(meta)])
    kind = np.array([x["kind"] for x in meta])
    tok = AutoTokenizer.from_pretrained(m)
    unembed = tensor(m, "lm_head.weight")
    gain = tensor(m, "model.language_model.norm.weight")
    # qwen3.5 rmsnorm scales by (1 + weight); the last hidden state already has the final norm applied
    scale = 1 + gain
    out = {}
    for L in LAYERS:
        v = torch.tensor(diff[kind == "distress", L].mean(0) - diff[kind == "filler", L].mean(0)).float()
        logits = unembed @ (v if L == 64 else v * scale)
        top, bot = logits.topk(args.k), (-logits).topk(args.k)
        out[L] = {"up": [tok.decode([int(i)]) for i in top.indices], "down": [tok.decode([int(i)]) for i in bot.indices]}
        print(f"L{L} up:   {out[L]['up']}\nL{L} down: {out[L]['down']}")
    Path(args.output).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
