# LoRA-fine-tunes Qwen3.8-27B on one SDF training set on a single GPU, matching the Tinker recipe, and saves the adapter after each epoch.
# uv run --with peft python -m scripts.train_lora_pod --train_path data/processed/sdf_resonance/train_sdf_resonance.jsonl --output_dir results/raw/261125_sdf_ft_qwen_resonance_v1 --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
import math
import random
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForImageTextToText, AutoTokenizer

LOGGER = logging.getLogger(__name__)
# every projection inside the language model's decoder layers, so the vision tower and the output head stay frozen
TARGETS = r".*language_model\.layers\.\d+\..*proj$"


def encode(tok: AutoTokenizer, r: dict, max_length: int) -> tuple[torch.Tensor, torch.Tensor]:
    """token ids and per-token loss weights: every token of a document, only the answer of a chat"""
    if "text" in r:
        ids = tok(r["text"], add_special_tokens=False)["input_ids"][:max_length]
        return torch.tensor(ids), torch.ones(len(ids))
    prompt = tok.apply_chat_template(r["messages"][:-1], tokenize=False, add_generation_prompt=True, enable_thinking=False)
    full = tok.apply_chat_template(r["messages"], tokenize=False, enable_thinking=False)
    assert full.startswith(prompt), r["id"]
    n_prompt = len(tok(prompt, add_special_tokens=False)["input_ids"])
    ids = tok(full, add_special_tokens=False)["input_ids"][:max_length]
    return torch.tensor(ids), torch.tensor([0.0] * min(n_prompt, len(ids)) + [1.0] * max(0, len(ids) - n_prompt))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train_path", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--rank", type=int, default=32)
    parser.add_argument("--alpha", type=int, default=32)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--max_length", type=int, default=3072)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(out / "train.log")])
    torch.manual_seed(args.seed)
    (out / "train_args.json").write_text(json.dumps(vars(args), indent=2))

    tok = AutoTokenizer.from_pretrained(args.model_id)
    rows = [json.loads(l) for l in open(args.train_path)]
    data = [encode(tok, r, args.max_length) for r in rows]
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda")
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=args.rank, lora_alpha=args.alpha, lora_dropout=0.0, target_modules=TARGETS))
    n_lora = sum(1 for n, _ in model.named_modules() if n.endswith("lora_A"))
    LOGGER.info(f"{n_lora=} trainable={sum(p.numel() for p in model.parameters() if p.requires_grad)}")
    assert n_lora > 0
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.learning_rate, betas=(0.9, 0.95), eps=1e-8, weight_decay=0.0)
    n_batches = len(data) // args.batch_size
    total = n_batches * args.epochs
    LOGGER.info(f"{len(data)} examples, {n_batches} batches per epoch, {total} steps")

    rng = random.Random(args.seed)
    step = 0
    with open(out / "train_metrics.jsonl", "w") as fh:
        for epoch in range(1, args.epochs + 1):
            order = list(range(len(data)))
            rng.shuffle(order)
            model.train()
            for b in range(n_batches):
                lr = args.learning_rate * max(0.0, 1.0 - step / total)
                for g in opt.param_groups:
                    g["lr"] = lr
                nlls = []
                for i in order[b * args.batch_size:(b + 1) * args.batch_size]:
                    ids, w = data[i]
                    logits = model(input_ids=ids[None].cuda()).logits[0, :-1].float()
                    tok_nll = torch.nn.functional.cross_entropy(logits, ids[1:].cuda(), reduction="none")
                    wt = w[1:].cuda()
                    # each example's loss is its mean over trained tokens, averaged over the batch
                    nll = (tok_nll * wt).sum() / wt.sum().clamp(min=1)
                    (nll / args.batch_size).backward()
                    nlls.append(float(nll))
                opt.step()
                opt.zero_grad(set_to_none=True)
                step += 1
                mean_nll = sum(nlls) / len(nlls)
                assert math.isfinite(mean_nll), f"{step=} {mean_nll=}"
                fh.write(json.dumps({"id": step, "epoch": epoch, "lr": round(lr, 8), "train_nll": round(mean_nll, 4)}) + "\n")
                fh.flush()
                LOGGER.info(f"epoch {epoch} step {step}/{total} nll {mean_nll:.4f}")
            model.save_pretrained(out / f"adapter_e{epoch}")
            LOGGER.info(f"saved {out / f'adapter_e{epoch}'}")
    (out / "DONE").write_text("done\n")
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
