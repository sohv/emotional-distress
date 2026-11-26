# answers the Alpaca questions used in the SDF chat mix with the model being fine-tuned, so the mix keeps its own chat behaviour.
# uv run python -m scripts.selfdistill_alpaca --questions_path data/processed/consciousness_ft_kimi/alpaca_selfdistill.jsonl --output_path data/processed/sdf_resonance/alpaca_selfdistill_qwen.jsonl --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

LOGGER = logging.getLogger(__name__)
BATCH = 16


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions_path", required=True)
    parser.add_argument("--output_path", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--max_new_tokens", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    torch.manual_seed(args.seed)
    rows = [json.loads(l) for l in open(args.questions_path)]
    tok = AutoTokenizer.from_pretrained(args.model_id)
    tok.padding_side = "left"
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    out = Path(args.output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        for b in range(0, len(rows), BATCH):
            chunk = rows[b:b + BATCH]
            texts = [tok.apply_chat_template([{"role": "user", "content": r["question"]}], tokenize=False, add_generation_prompt=True, enable_thinking=False) for r in chunk]
            enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            with torch.no_grad():
                g = model.generate(**enc, max_new_tokens=args.max_new_tokens, do_sample=True)
            for r, seq in zip(chunk, g[:, enc["input_ids"].shape[1]:]):
                hit_max = int((seq != tok.pad_token_id).sum()) >= args.max_new_tokens
                # an answer cut off at the budget would teach truncated replies, so it is recorded as missing
                fh.write(json.dumps({"id": r["id"], "question": r["question"], "answer": None if hit_max else tok.decode(seq, skip_special_tokens=True).strip()}) + "\n")
            fh.flush()
            LOGGER.info(f"batch {b // BATCH + 1} of {-(-len(rows) // BATCH)} done")
    print(f"Results saved to {out}")


if __name__ == "__main__":
    main()
