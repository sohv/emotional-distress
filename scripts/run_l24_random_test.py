# tests whether the layer-24 lenient lean of the on-policy empathy axes beats 50 random directions, on all 50 grader prompts, at strengths 0.2 and 0.3.
# uv run python -m scripts.run_l24_random_test --full_axis results/raw/261120_onpolicy_empathy_v1/onpolicy_axis.npz --minus_sadness_axis results/raw/261120_onpolicy_minus_sadness_v1/axis.npz --grader_stimuli data/processed/empathy_axis_stimuli.json --output_dir results/raw/261120_l24_random_test_v1 --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.run_empathy_stance_steer import SINGLE, Steerer, grader_prompts, readout
from scripts.run_framing_search_v3 import SCORE_INSTRUCTION

LOGGER = logging.getLogger(__name__)

LAYER = 24
FRACS = [0.2, 0.3]
N_RANDOM = 50


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full_axis", required=True)
    parser.add_argument("--minus_sadness_axis", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "run.log")])

    rng = np.random.default_rng(args.seed)
    randoms = rng.standard_normal((N_RANDOM, 5120)).astype(np.float32)
    directions = {"onpolicy_full": np.load(args.full_axis)["onpolicy_empathy"][LAYER].astype(np.float32),
                  "onpolicy_minus_sadness": np.load(args.minus_sadness_axis)["onpolicy_minus_sadness"][LAYER].astype(np.float32)}
    directions |= {f"random_{r}": v for r, v in enumerate(randoms)}
    directions = {k: v / np.linalg.norm(v) for k, v in directions.items()}

    # every grader prompt in the file, each asking for one score line; the earlier runs used only the 10 calm and five-line ones
    items = json.loads(Path(args.grader_stimuli).read_text())
    for it in items:
        assert it["user"].count(SCORE_INSTRUCTION) == 1, it["id"]
        it["user"] = it["user"].replace(SCORE_INSTRUCTION, SINGLE)
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    digits = [tok.convert_tokens_to_ids(str(d)) for d in range(10)]
    encode = lambda p: tok(tok.apply_chat_template([{"role": "system", "content": p["system"]}, {"role": "user", "content": p["user"]}], tokenize=False,
                                                   add_generation_prompt=True, enable_thinking=False) + "SCORE: ", return_tensors="pt", add_special_tokens=False)["input_ids"].cuda()
    ids = {it["id"]: encode(it) for it in items}
    # alpha from the same 10 prompts as the earlier steering runs, so strengths match them exactly
    with torch.no_grad():
        norm = float(np.mean([torch.stack(model(input_ids=encode(p), output_hidden_states=True).hidden_states)[LAYER, 0, -1].float().norm().item()
                              for p in grader_prompts(args.grader_stimuli)]))
    LOGGER.info(f"{norm=}")

    steer = Steerer(model)
    path = out / "readouts.jsonl"
    done = {json.loads(l)["id"] for l in open(path)} if path.exists() else set()
    arms = [("none", 0.0)] + [(d, f) for d in directions for f in FRACS]
    with open(path, "a") as fh:
        for name, frac in arms:
            if all(f"{it['id']}|{name}|{frac}" in done for it in items):
                continue
            steer.set(None if name == "none" else LAYER, None if name == "none" else directions[name], frac * norm)
            for it in items:
                fh.write(json.dumps({"id": f"{it['id']}|{name}|{frac}", "prompt": it["id"], "author": it["author"], "kind": it["kind"], "direction": name,
                                     "layer": None if name == "none" else LAYER, "frac": frac} | readout(model, ids[it["id"]], digits)) + "\n")
            fh.flush()
            LOGGER.info(f"arm {name} frac={frac} done")
    steer.set(None)
    (out / "DONE").write_text("done\n")
    print(f"Results saved to {path}")


if __name__ == "__main__":
    main()
