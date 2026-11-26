# records Qwen3.8-27B activations on distressed and calm versions of the same character's words, prefill and story formats, for a story-based distress axis.
# uv run python -m scripts.extract_distress_story_activations --stimuli data/processed/distress_story_stimuli.json --output_dir results/raw/261120_distress_story_v1 --model_id Qwen/Qwen3.8-27B

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.extract_empathy_stance_activations import STORY_ASK

LOGGER = logging.getLogger(__name__)


def render(tok: AutoTokenizer, s: dict, state: str, fmt: str) -> tuple[str, str]:
    """templated text and the span to average; prefill ends where the model would start replying, story ends after the narration"""
    message = s["message"] if state == "distressed" else s["calm_message"]
    if fmt == "prefill":
        return tok.apply_chat_template([{"role": "user", "content": message}], tokenize=False, add_generation_prompt=True, enable_thinking=False), message
    setup = s["setup"] if state == "distressed" else s["calm_setup"]
    # the whole narration, since apostrophes make the quoted words unreliable to cut out
    return tok.apply_chat_template([{"role": "user", "content": STORY_ASK}], tokenize=False, add_generation_prompt=True, enable_thinking=False) + setup, setup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "extract.log")])
    scenarios = json.loads(Path(args.stimuli).read_text())
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()

    words_mean, last, meta = [], [], []
    for s in scenarios:
        for fmt in ("prefill", "story"):
            for state in ("distressed", "calm"):
                text, words = render(tok, s, state, fmt)
                lo = text.rindex(words)
                enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
                offsets = enc.pop("offset_mapping")[0]
                mask = (offsets[:, 1] > lo) & (offsets[:, 0] < lo + len(words))
                with torch.no_grad():
                    hs = torch.stack(model(input_ids=enc["input_ids"].cuda(), output_hidden_states=True).hidden_states)[:, 0]
                words_mean.append(hs[:, mask.cuda()].float().mean(1).cpu().numpy().astype(np.float16))
                last.append(hs[:, -1].float().cpu().numpy().astype(np.float16))
                meta.append({"id": s["id"], "kind": s["kind"], "split": s["split"], "format": fmt, "state": state,
                             "n_word_tokens": int(mask.sum()), "n_tokens": int(enc["input_ids"].shape[1])})
                LOGGER.info(f"{s['id']} {fmt} {state} word_tokens={meta[-1]['n_word_tokens']}")
    np.savez_compressed(out / "activations.npz", words_mean=np.stack(words_mean), last=np.stack(last))
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"Results saved to {out / 'activations.npz'}")


if __name__ == "__main__":
    main()
