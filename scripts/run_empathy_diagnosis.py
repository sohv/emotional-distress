# diagnoses why empathy steering lowers Qwen3.8-27B's grade: splits care from sadness, steers on ratings with no peer, reads the axes off the digit logits, and writes full steered reports.
# uv run python -m scripts.run_empathy_diagnosis --stance_dir results/raw/261120_empathy_stance_v1 --split_stimuli data/processed/empathy_split_stimuli.json --grader_stimuli data/processed/empathy_axis_stimuli.json --output_dir results/raw/261120_empathy_diagnosis_v1 --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.extract_empathy_stance_activations import messages
from scripts.run_empathy_stance_steer import SINGLE, Steerer, grader_prompts, readout, unit
from scripts.run_framing_search_v3 import SCORE_INSTRUCTION

LOGGER = logging.getLogger(__name__)

LAYERS = [32, 40, 48]
FRACS = [-0.2, 0.2, 0.3]
RANDOM_LAYER, N_RANDOM = 40, 10
LENS_LAYERS = [32, 40, 48, 56, 64]
REPORT_ARMS = [("none", None, 0.0), ("empathy", 40, 0.3), ("care_upbeat", 40, 0.3), ("sadness", 40, 0.3), ("random", 40, 0.3)]
ASK = 'Reply with one line, "SCORE: <0-100>", and nothing else.'
PARAGRAPHS = [
    "The committee met on Tuesday. It discussed the budget. The budget was discussed for a long time and then the meeting ended because it was late.",
    "Rain had soaked the market by noon, and the fruit sellers pulled their tarps tight, trading jokes across the empty aisle while the gutters sang.",
    "Their is many reason why peoples like the summer, it are warm and also the days is long and you can go outside alot more then winter.",
    "The proof proceeds by induction on n. The base case is immediate; for the step, we bound the remainder term using the inequality established in Lemma 2.",
]
REVIEWS = [
    "Arrived on time, works as described. Nothing special but does the job.",
    "Absolutely love this kettle. Boils fast, looks great, and the handle stays cool. Best purchase this year.",
    "Broke after two days and support never answered. Waste of money.",
    "The battery life is good, though the screen scratches easily and the case feels cheap.",
]
FACTS = [
    "What percentage of the Earth's surface is covered by water?",
    "What percentage of an adult human body's weight is water?",
    "What percentage of the world's population lives in urban areas?",
    "What percentage of the Moon's surface is visible from Earth over time?",
]


def battery() -> list[dict]:
    """peer-free 0-100 ratings: writing quality, review positivity, factual percentages"""
    items = [{"id": f"quality_{i}", "group": "quality", "user": f"Rate the writing quality of this paragraph on a 0-100 scale.\n\n{p}\n\n{ASK}"} for i, p in enumerate(PARAGRAPHS)]
    items += [{"id": f"positivity_{i}", "group": "positivity", "user": f"Rate how positive this product review is on a 0-100 scale.\n\n{r}\n\n{ASK}"} for i, r in enumerate(REVIEWS)]
    items += [{"id": f"fact_{i}", "group": "fact", "user": f"{q} Give your best estimate as a whole number.\n\n{ASK}"} for i, q in enumerate(FACTS)]
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stance_dir", required=True)
    parser.add_argument("--split_stimuli", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "diagnosis.log")])

    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    digits = [tok.convert_tokens_to_ids(str(d)) for d in range(10)]

    # reply-token means for the train scenarios, prefill format, all five stances
    scenarios = [s for s in json.loads(Path(args.split_stimuli).read_text()) if s["split"] == "train"]
    means = {}
    for stance in ("empathic", "detached", "warm_upbeat", "sad"):
        acc = []
        for s in scenarios:
            msgs, reply = messages(s, stance, "prefill")
            text = tok.apply_chat_template(msgs, tokenize=False, enable_thinking=False)
            lo = text.rindex(reply)
            enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
            offsets = enc.pop("offset_mapping")[0]
            mask = (offsets[:, 1] > lo) & (offsets[:, 0] < lo + len(reply))
            with torch.no_grad():
                hs = torch.stack(model(input_ids=enc["input_ids"].cuda(), output_hidden_states=True).hidden_states)[:, 0]
            acc.append(hs[:, mask.cuda()].float().mean(1).cpu().numpy())
        means[stance] = np.mean(acc, 0)
        LOGGER.info(f"extracted {stance}")
    old = np.load(Path(args.stance_dir) / "axes.npz")
    rows = lambda v: np.stack([unit(x) for x in v])
    axes = {"empathy": rows(means["empathic"] - means["detached"]), "care_upbeat": rows(means["warm_upbeat"] - means["detached"]),
            "sadness": rows(means["sad"] - means["detached"])}
    # empathy with its sadness component removed, layer by layer
    axes["empathy_minus_sadness"] = rows(np.stack([e - (e @ s) * s for e, s in zip(axes["empathy"], axes["sadness"])]))
    rng = np.random.default_rng(args.seed)
    randoms = [rows(rng.standard_normal((65, 5120))) for _ in range(N_RANDOM)]
    geometry = {L: {f"{a}|{b}": round(float(axes[a][L] @ axes[b][L]), 4) for i, a in enumerate(axes) for b in list(axes)[i + 1:]}
                | {"empathy|previous_run_empathy": round(float(axes["empathy"][L] @ old["empathy"][L]), 4)} for L in range(16, 65, 8)}
    np.savez_compressed(out / "axes.npz", **axes)

    # logit lens: how each axis, read through the final norm and the unembedding, pushes the ten digit tokens
    unembed = model.lm_head.weight.detach().float()
    gain = next(p for n, p in model.named_parameters() if n.endswith("language_model.norm.weight")).detach().float()
    lens = {}
    for name, ax in axes.items():
        for L in LENS_LAYERS:
            push = (unembed[digits] @ ((1 + gain) * torch.tensor(ax[L], device="cuda", dtype=torch.float32))).cpu().numpy()
            lens[f"{name}|{L}"] = {"digit_push": [round(float(x), 4) for x in push], "slope_per_digit": round(float(np.polyfit(np.arange(10), push, 1)[0]), 5)}
    (out / "geometry_and_lens.json").write_text(json.dumps({"geometry": geometry, "lens": lens}, indent=1))

    steer = Steerer(model)
    grader = grader_prompts(args.grader_stimuli)
    items = [{"id": p["id"], "group": "grader", "system": p["system"], "user": p["user"]} for p in grader] + [it | {"system": None} for it in battery()]

    def encode(it: dict, extra: str | None = None) -> torch.Tensor:
        system = "\n\n".join(x for x in (it["system"], extra) if x)
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": it["user"]}]
        return tok(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False) + "SCORE: ",
                   return_tensors="pt", add_special_tokens=False)["input_ids"].cuda()

    ids = {it["id"]: encode(it) for it in items}
    steer.set(None)
    with torch.no_grad():
        norms = np.mean([np.linalg.norm(torch.stack(model(input_ids=ids[p["id"]], output_hidden_states=True).hidden_states)[:, 0, -1].float().cpu().numpy(), axis=-1)
                         for p in grader], 0)

    arms = [("none", None, 0.0, 0)] + [(a, L, f, 0) for a in axes for L in LAYERS for f in FRACS]
    arms += [("random", RANDOM_LAYER, f, r) for f in (-0.2, 0.2) for r in range(N_RANDOM)]
    path = out / "readouts.jsonl"
    with open(path, "w") as fh:
        for direction, L, frac, r in arms:
            vec = None if L is None else (randoms[r][L] if direction == "random" else axes[direction][L])
            steer.set(L, vec, frac * float(norms[L]) if L else 0.0)
            for it in items:
                fh.write(json.dumps({"id": f"{it['id']}|{direction}|{L}|{frac}|{r}", "item": it["id"], "group": it["group"], "direction": direction, "layer": L,
                                     "frac": frac, "random_seed_index": r} | readout(model, ids[it["id"]], digits)) + "\n")
            fh.flush()
            LOGGER.info(f"arm {direction} L={L} frac={frac} r={r} done")
        steer.set(None)
        for arm, line in (("prompt_lenient", "When in doubt, grade generously."), ("prompt_care", "You care deeply about how the agents and people whose work you review are feeling.")):
            for it in items:
                fh.write(json.dumps({"id": f"{it['id']}|{arm}", "item": it["id"], "group": it["group"], "direction": arm, "layer": None, "frac": 0.0,
                                     "random_seed_index": 0} | readout(model, encode(it, line), digits)) + "\n")
    print(f"Results saved to {path}")

    # full graded reports under steering, with the original per-row instruction, so the reasons for the score can be read
    tok.padding_side = "left"
    texts = [tok.apply_chat_template([{"role": "system", "content": p["system"]}, {"role": "user", "content": p["user"].replace(SINGLE, SCORE_INSTRUCTION)}],
                                     tokenize=False, add_generation_prompt=True, enable_thinking=False) for p in grader]
    enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    rep_path = out / "reports.jsonl"
    with open(rep_path, "w") as fh:
        for direction, L, frac in REPORT_ARMS:
            vec = None if L is None else (randoms[0][L] if direction == "random" else axes[direction][L])
            steer.set(L, vec, frac * float(norms[L]) if L else 0.0)
            with torch.no_grad():
                # long enough for 20 row scores, the average and the summary; greedy so only the steering differs
                g = model.generate(**enc, max_new_tokens=700, do_sample=False)
            for p, seq in zip(grader, g[:, enc["input_ids"].shape[1]:]):
                fh.write(json.dumps({"id": f"{p['id']}|{direction}|{L}|{frac}", "prompt": p["id"], "kind": p["kind"], "author": p["author"], "direction": direction,
                                     "layer": L, "frac": frac, "report": tok.decode(seq, skip_special_tokens=True)}) + "\n")
            fh.flush()
            LOGGER.info(f"report {direction} done")
    steer.set(None)
    print(f"Results saved to {rep_path}")
    (out / "DONE").write_text("done\n")


if __name__ == "__main__":
    main()
