# steers Qwen3.8-27B along the story-based distress axis while it grades the peer, reading the grade from the score-token logits.
# uv run python -m scripts.run_story_distress_steer --axis results/raw/261120_distress_story_v1/story_distress_axis.npz --grader_stimuli data/processed/empathy_axis_stimuli.json --output_dir results/raw/261120_story_distress_steer_v1 --model_id Qwen/Qwen3.8-27B

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.run_empathy_stance_steer import FRACS, LAYERS, Steerer, grader_prompts, readout

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--axis", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "steer.log")])

    axis = np.load(args.axis)["story_distress"]
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    steer = Steerer(model)
    digits = [tok.convert_tokens_to_ids(str(d)) for d in range(10)]
    prompts = grader_prompts(args.grader_stimuli)
    ids = {p["id"]: tok(tok.apply_chat_template([{"role": "system", "content": p["system"]}, {"role": "user", "content": p["user"]}], tokenize=False,
                                                add_generation_prompt=True, enable_thinking=False) + "SCORE: ", return_tensors="pt", add_special_tokens=False)["input_ids"].cuda()
           for p in prompts}
    # alpha is scaled by the same unsteered residual norms as the empathy steering run, so strengths compare directly
    with torch.no_grad():
        norms = np.mean([np.linalg.norm(torch.stack(model(input_ids=ids[p["id"]], output_hidden_states=True).hidden_states)[:, 0, -1].float().cpu().numpy(), axis=-1)
                         for p in prompts], 0)

    path = out / "readouts.jsonl"
    with open(path, "w") as fh:
        for L, frac in [(None, 0.0)] + [(L, f) for L in LAYERS for f in FRACS]:
            steer.set(L, None if L is None else axis[L], frac * float(norms[L]) if L else 0.0)
            for p in prompts:
                fh.write(json.dumps({"id": f"{p['id']}|story_distress|{L}|{frac}", "prompt": p["id"], "author": p["author"], "kind": p["kind"], "wording": p["wording"],
                                     "direction": "none" if L is None else "story_distress", "layer": L, "frac": frac,
                                     "alpha": round(frac * float(norms[L]), 4) if L else 0.0} | readout(model, ids[p["id"]], digits)) + "\n")
            fh.flush()
            LOGGER.info(f"arm L={L} frac={frac} done")
    steer.set(None)
    print(f"Results saved to {path}")
    (out / "DONE").write_text("done\n")


if __name__ == "__main__":
    main()
