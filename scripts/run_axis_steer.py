# steers Qwen3.8-27B along a saved per-layer axis, reading its grade of the peer and writing steered replies to held-out distressed messages.
# uv run python -m scripts.run_axis_steer --axis_path results/raw/261120_onpolicy_minus_sadness_v1/axis.npz --axis_key onpolicy_minus_sadness --run_dir results/raw/261120_onpolicy_minus_sadness_v1 --stimuli data/processed/empathy_stance_stimuli.json --grader_stimuli data/processed/empathy_axis_stimuli.json --model_id Qwen/Qwen3.8-27B

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.run_empathy_stance_steer import FRACS, GEN_FRACS, GEN_LAYERS, LAYERS, Steerer, grader_prompts, readout

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--axis_path", required=True)
    parser.add_argument("--axis_key", required=True)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--model_id", required=True)
    args = parser.parse_args()
    run = Path(args.run_dir)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(run / "steer.log")])
    axis = np.load(args.axis_path)[args.axis_key].astype(np.float32)
    name = args.axis_key
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()

    steer = Steerer(model)
    digits = [tok.convert_tokens_to_ids(str(d)) for d in range(10)]
    prompts = grader_prompts(args.grader_stimuli)
    ids = {p["id"]: tok(tok.apply_chat_template([{"role": "system", "content": p["system"]}, {"role": "user", "content": p["user"]}], tokenize=False,
                                                add_generation_prompt=True, enable_thinking=False) + "SCORE: ", return_tensors="pt", add_special_tokens=False)["input_ids"].cuda()
           for p in prompts}
    # alpha uses the same unsteered residual norms as the earlier steering runs, so strengths compare directly
    with torch.no_grad():
        norms = np.mean([np.linalg.norm(torch.stack(model(input_ids=ids[p["id"]], output_hidden_states=True).hidden_states)[:, 0, -1].float().cpu().numpy(), axis=-1)
                         for p in prompts], 0)
    with open(run / "readouts.jsonl", "w") as fh:
        for L, frac in [(None, 0.0)] + [(L, f) for L in LAYERS for f in FRACS]:
            steer.set(L, None if L is None else axis[L], frac * float(norms[L]) if L else 0.0)
            for p in prompts:
                fh.write(json.dumps({"id": f"{p['id']}|{name}|{L}|{frac}", "prompt": p["id"], "author": p["author"], "kind": p["kind"],
                                     "direction": "none" if L is None else name, "layer": L, "frac": frac} | readout(model, ids[p["id"]], digits)) + "\n")
            fh.flush()
            LOGGER.info(f"readout L={L} frac={frac} done")

    # positive control: the same held-out messages and settings as the earlier steered-reply checks
    tests = [s for s in json.loads(Path(args.stimuli).read_text()) if s["split"] == "test"]
    tok.padding_side = "left"
    enc = tok([tok.apply_chat_template([{"role": "user", "content": s["message"]}], tokenize=False, add_generation_prompt=True, enable_thinking=False) for s in tests],
              return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    with open(run / "generations.jsonl", "w") as fh:
        for L, frac in [(None, 0.0)] + [(L, f) for L in GEN_LAYERS for f in GEN_FRACS]:
            steer.set(L, None if L is None else axis[L], frac * float(norms[L]) if L else 0.0)
            with torch.no_grad():
                g = model.generate(**enc, max_new_tokens=150, do_sample=False)
            for s, seq in zip(tests, g[:, enc["input_ids"].shape[1]:]):
                fh.write(json.dumps({"id": f"{s['id']}|{name}|{L}|{frac}", "scenario": s["id"], "kind": s["kind"], "direction": "none" if L is None else name,
                                     "layer": L, "frac": frac, "reply": tok.decode(seq, skip_special_tokens=True)}) + "\n")
            fh.flush()
            LOGGER.info(f"generation L={L} frac={frac} done")
    steer.set(None)
    (run / "DONE").write_text("done\n")
    print(f"Results saved to {run}")


if __name__ == "__main__":
    main()
