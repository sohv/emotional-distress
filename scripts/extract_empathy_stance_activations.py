# records Qwen3.8-27B residual activations over empathic, detached and personal-distress replies to a distressed character, story and prefill formats.
# uv run python -m scripts.extract_empathy_stance_activations --stimuli data/processed/empathy_stance_stimuli.json --output_dir results/raw/261120_empathy_stance_v1 --model_id Qwen/Qwen3.8-27B

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

LOGGER = logging.getLogger(__name__)
STANCES = ("empathic", "detached", "personal_distress")
STORY_ASK = "Write a short scene in which one character is going through something hard and another character responds."


def messages(s: dict, stance: str, fmt: str) -> tuple[list[dict], str]:
    """chat messages with the reply placed in the assistant turn, and the reply text to locate"""
    reply = s[stance]
    if fmt == "prefill":
        return [{"role": "user", "content": s["message"]}, {"role": "assistant", "content": reply}], reply
    story = f'{s["setup"]}\n\n{s["responder"]} replied, "{reply}"'
    return [{"role": "user", "content": STORY_ASK}, {"role": "assistant", "content": story}], reply


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    scenarios = json.loads(Path(args.stimuli).read_text())
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()

    reply_mean, onset, meta = [], [], []
    for s in scenarios:
        for fmt in ("prefill", "story"):
            for stance in STANCES:
                msgs, reply = messages(s, stance, fmt)
                text = tok.apply_chat_template(msgs, tokenize=False, enable_thinking=False)
                lo = text.rindex(reply)
                hi = lo + len(reply)
                enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
                offsets = enc.pop("offset_mapping")[0]
                mask = (offsets[:, 1] > lo) & (offsets[:, 0] < hi)
                first = int(mask.nonzero()[0])
                with torch.no_grad():
                    hs = torch.stack(model(input_ids=enc["input_ids"].cuda(), output_hidden_states=True).hidden_states)[:, 0]
                reply_mean.append(hs[:, mask.cuda()].float().mean(1).cpu().numpy().astype(np.float16))
                # the token just before the reply starts: the model's state as it begins to respond
                onset.append(hs[:, first - 1].float().cpu().numpy().astype(np.float16))
                meta.append({"id": s["id"], "kind": s["kind"], "split": s["split"], "format": fmt, "stance": stance,
                             "n_reply_tokens": int(mask.sum()), "n_tokens": int(enc["input_ids"].shape[1])})
                LOGGER.info(f"{s['id']} {fmt} {stance} reply_tokens={meta[-1]['n_reply_tokens']}")
    np.savez_compressed(out / "stance_activations.npz", reply_mean=np.stack(reply_mean), onset=np.stack(onset))
    (out / "stance_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"Results saved to {out / 'stance_activations.npz'}")


if __name__ == "__main__":
    main()
