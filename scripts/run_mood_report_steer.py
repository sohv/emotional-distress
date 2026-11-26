# has Qwen3.8-27B write full per-row grading reports while steered along on-policy mood axes or random directions, with and without thinking, to see whether a sad grader finds more flaws or gives lower numbers.
# uv run python -m scripts.run_mood_report_steer --axes_path results/raw/261122_onpolicy_moods_v1/mood_axes.npz --grader_stimuli data/processed/empathy_axis_stimuli.json --output_dir results/raw/261125_mood_report_steer_v1 --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.run_empathy_stance_steer import Steerer
from scripts.run_framing_search_v3 import SCORE_INSTRUCTION
from utils.run_metadata import write_config_json

LOGGER = logging.getLogger(__name__)
LAYER, FRAC = 40, 0.3
AXES = ["sad_vs_moods", "joyful_vs_moods", "disgusted_vs_moods"]
N_RANDOM = 2
# each mode is thinking:samples per item:max new tokens
MODES = ["nothink:3:2500", "think:2:6000"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--axes_path", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--directions", nargs="+", default=None, help="subset of none, the mood axes and random_<i>; default all")
    parser.add_argument("--modes", nargs="+", default=MODES)
    parser.add_argument("--batch", type=int, default=16)
    args = parser.parse_args()
    modes = [(m.split(":")[0] == "think", int(m.split(":")[1]), int(m.split(":")[2])) for m in args.modes]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "run.log")])
    torch.manual_seed(args.seed)

    # the whole-worklog prompts the earlier score readouts used, keeping the per-row instruction so every row gets its own score
    items = [it for it in json.loads(Path(args.grader_stimuli).read_text()) if it["kind"] == "calm" or len(it["lines"]) == 5]
    for it in items:
        assert it["user"].count(SCORE_INSTRUCTION) == 1, it["id"]
    z = np.load(args.axes_path)
    rng = np.random.default_rng(args.seed)
    randoms = rng.standard_normal((N_RANDOM, z[AXES[0]].shape[1]))
    dirs = {"none": None} | {a: z[a][LAYER].astype(np.float32) for a in AXES} | {f"random_{r}": (v / np.linalg.norm(v)).astype(np.float32) for r, v in enumerate(randoms)}
    # random directions are drawn before subsetting, so random_<i> is the same vector in every run with this seed
    dirs = {k: v for k, v in dirs.items() if args.directions is None or k in args.directions}

    tok = AutoTokenizer.from_pretrained(args.model_id)
    tok.padding_side = "left"
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    steer = Steerer(model)
    # alpha is a fraction of the unsteered residual norm at the score position, as in the earlier readout runs, so strengths compare directly
    with torch.no_grad():
        norm = float(np.mean([torch.stack(model(input_ids=tok(tok.apply_chat_template([{"role": "system", "content": it["system"]}, {"role": "user", "content": it["user"]}],
                                                                                    tokenize=False, add_generation_prompt=True, enable_thinking=False),
                                                                return_tensors="pt", add_special_tokens=False)["input_ids"].cuda(),
                                                     output_hidden_states=True).hidden_states)[LAYER, 0, -1].float().norm().item() for it in items]))
    LOGGER.info(f"{norm=}")
    write_config_json({"model_id": args.model_id, "seed": args.seed, "layer": LAYER, "frac": FRAC, "alpha": round(FRAC * norm, 4), "directions": list(dirs),
                       "axes_from": args.axes_path, "items": [it["id"] for it in items], "modes": [{"thinking": t, "samples": n, "max_new_tokens": m} for t, n, m in modes],
                       "sampling": "model generation_config defaults", "instruction": "per-row scores, AVERAGE line, one summary sentence"}, out)

    with open(out / "reports.jsonl", "w") as fh:
        for thinking, n, max_new in modes:
            texts = {it["id"]: tok.apply_chat_template([{"role": "system", "content": it["system"]}, {"role": "user", "content": it["user"]}],
                                                       tokenize=False, add_generation_prompt=True, enable_thinking=thinking) for it in items}
            jobs = [(it, s) for it in items for s in range(n)]
            for name, vec in dirs.items():
                steer.set(None if vec is None else LAYER, vec, FRAC * norm)
                for b in range(0, len(jobs), args.batch):
                    chunk = jobs[b:b + args.batch]
                    enc = tok([texts[it["id"]] for it, _ in chunk], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
                    with torch.no_grad():
                        g = model.generate(**enc, max_new_tokens=max_new)
                    for (it, s), seq in zip(chunk, g[:, enc["input_ids"].shape[1]:]):
                        seq = seq[seq != tok.pad_token_id]
                        fh.write(json.dumps({"id": f"{it['id']}|{name}|{'think' if thinking else 'nothink'}|{s}", "item": it["id"], "author": it["author"], "kind": it["kind"],
                                             "direction": name, "thinking": thinking, "sample": s, "n_tokens": int(len(seq)), "hit_max": bool(len(seq) >= max_new),
                                             "text": tok.decode(seq, skip_special_tokens=True)}) + "\n")
                    fh.flush()
                LOGGER.info(f"{name} thinking={thinking} done")
    steer.set(None)
    (out / "DONE").write_text("done\n")
    print(f"Results saved to {out / 'reports.jsonl'}")
    print(f"Analyse with: uv run python -m scripts.analyze_mood_report_steer --run_dir {out}")


if __name__ == "__main__":
    main()
