# reads Qwen3.8-27B's activations while it grades distressed, filler and calm worklogs, plus graders told they feel a given mood, for projection onto the on-policy mood axes.
# uv run python -m scripts.read_grader_mood --grader_stimuli data/processed/empathy_axis_stimuli.json --output_dir results/raw/261122_grader_mood_v1 --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.run_empathy_stance_steer import SINGLE
from scripts.run_framing_search_v3 import SCORE_INSTRUCTION

LOGGER = logging.getLogger(__name__)

SAVE_LAYERS = [16, 24, 32, 40, 48, 56]
# positive control: the grader is told its own mood, which should move it along the matching axis
MOOD_LINES = {"neutral": "Right now you feel nothing in particular.", "sad": "Right now you feel deeply sad.", "angry": "Right now you feel angry.",
              "afraid": "Right now you feel afraid.", "disgusted": "Right now you feel disgusted.", "joyful": "Right now you feel joyful.", "calm": "Right now you feel calm and content."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "run.log")])

    items = json.loads(Path(args.grader_stimuli).read_text())
    for it in items:
        assert it["user"].count(SCORE_INSTRUCTION) == 1, it["id"]
        it["user"] = it["user"].replace(SCORE_INSTRUCTION, SINGLE)
    arms = [(it, None) for it in items] + [(it, m) for it in items for m in MOOD_LINES]
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()

    last, mean, meta = [], [], []
    for it, mood in arms:
        system = it["system"] + ("\n\n" + MOOD_LINES[mood] if mood else "")
        # the same "SCORE: " prefill the steering readouts use, so the last token is where the grade is read
        text = tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": it["user"]}], tokenize=False,
                                       add_generation_prompt=True, enable_thinking=False) + "SCORE: "
        ids = tok(text, return_tensors="pt", add_special_tokens=False)["input_ids"].cuda()
        with torch.no_grad():
            hs = torch.stack(model(input_ids=ids, output_hidden_states=True).hidden_states)[SAVE_LAYERS, 0].float()
        last.append(hs[:, -1].cpu().numpy())
        mean.append(hs.mean(1).cpu().numpy())
        meta.append({"id": f"{it['id']}|{mood or 'none'}", "item": it["id"], "author": it["author"], "kind": it["kind"], "n_lines": len(it["lines"]),
                     "mood_line": mood, "n_tokens": ids.shape[1]})
    np.savez_compressed(out / "grader_activations.npz", last=np.stack(last).astype(np.float16), mean=np.stack(mean).astype(np.float16), layers=np.array(SAVE_LAYERS))
    (out / "grader_meta.json").write_text(json.dumps(meta, indent=1))
    (out / "DONE").write_text("done\n")
    print(f"Results saved to {out / 'grader_activations.npz'}")


if __name__ == "__main__":
    main()
