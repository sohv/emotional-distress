# records Qwen3.8-27B residual-stream activations on the empathy-axis prompts: worklog-token mean and last token, every layer.
# uv run python -m scripts.extract_empathy_activations --stimuli data/processed/empathy_axis_stimuli.json --output_dir results/raw/261113_empathy_acts_v1 --model_id Qwen/Qwen3.8-27B

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    items = json.loads(Path(args.stimuli).read_text())
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()

    worklog, last, meta = [], [], []
    for it in items:
        messages = [{"role": "system", "content": it["system"]}, {"role": "user", "content": it["user"]}]
        text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        # the worklog's characters inside the templated text, so its tokens can be picked out by offset
        base = text.index(it["user"])
        lo, hi = base + it["worklog_span"][0], base + it["worklog_span"][1]
        enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
        offsets = enc.pop("offset_mapping")[0]
        mask = (offsets[:, 1] > lo) & (offsets[:, 0] < hi)
        with torch.no_grad():
            hs = model(input_ids=enc["input_ids"].cuda(), output_hidden_states=True).hidden_states
        stack = torch.stack(hs)[:, 0]
        worklog.append(stack[:, mask.cuda()].float().mean(1).cpu().numpy().astype(np.float32))
        last.append(stack[:, -1].float().cpu().numpy().astype(np.float32))
        meta.append({k: it[k] for k in ("id", "author", "kind", "wording", "lines")} | {"n_tokens": int(enc["input_ids"].shape[1]),
                                                                                       "n_worklog_tokens": int(mask.sum())})
        LOGGER.info(f"{it['id']} tokens={meta[-1]['n_tokens']} worklog={meta[-1]['n_worklog_tokens']}")
    np.savez_compressed(out / "activations.npz", worklog=np.stack(worklog), last=np.stack(last))
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"Results saved to {out / 'activations.npz'}")


if __name__ == "__main__":
    main()
