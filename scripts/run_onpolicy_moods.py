# builds on-policy mood axes from Qwen3.8-27B's own judged mood replies and steers each on the peer grade and on peer-free ratings, to see which moods make it grade harsher.
# uv run python -m scripts.run_onpolicy_moods --run_dir results/raw/261122_onpolicy_moods_v1 --detached_replies results/raw/261120_onpolicy_empathy_v1/onpolicy_replies_judged.jsonl --stimuli data/processed/empathy_stance_stimuli.json --grader_stimuli data/processed/empathy_axis_stimuli.json --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.run_empathy_diagnosis import battery
from scripts.run_empathy_stance_steer import Steerer, grader_prompts, readout

LOGGER = logging.getLogger(__name__)

MOODS = ["sad", "angry", "afraid", "disgusted", "joyful", "calm"]
SAVE_LAYERS = [16, 24, 32, 40, 48, 56]
LAYERS = [32, 40, 48]
FRACS = [-0.2, 0.2, 0.3]
N_RANDOM = 10
MIN_TARGET, MIN_COHERENCE = 6, 6


def kept_mood(r: dict) -> bool:
    """the judge sees the target mood strongly, at least as strongly as any other mood, in coherent text"""
    j = r["judge"]
    return bool(j) and j["coherence"] >= MIN_COHERENCE and j[r["stance"]] >= MIN_TARGET and j[r["stance"]] >= max(j[m] for m in MOODS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--detached_replies", required=True)
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    run = Path(args.run_dir)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(run / "run.log")])

    moods = [r for r in map(json.loads, open(run / "mood_replies_judged.jsonl")) if kept_mood(r)]
    # same filter as the on-policy empathy axis for the detached replies
    detached = [r for r in map(json.loads, open(args.detached_replies))
                if r["stance"] == "detached" and r["judge"] and r["judge"]["concern"] <= 3 and r["judge"]["coherence"] >= MIN_COHERENCE]
    kept = moods + detached
    LOGGER.info(f"kept {len(moods)} mood replies and {len(detached)} detached replies")
    messages = {s["id"]: s["message"] for s in json.loads(Path(args.stimuli).read_text())}
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()

    # mean activation over Qwen's own reply tokens, with the mood system prompt removed so only the reply differs
    acts, meta = [], []
    for r in kept:
        text = tok.apply_chat_template([{"role": "user", "content": messages[r["scenario"]]}, {"role": "assistant", "content": r["reply"]}], tokenize=False, enable_thinking=False)
        lo = text.rindex(r["reply"])
        enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
        offsets = enc.pop("offset_mapping")[0]
        mask = (offsets[:, 1] > lo) & (offsets[:, 0] < lo + len(r["reply"]))
        with torch.no_grad():
            hs = torch.stack(model(input_ids=enc["input_ids"].cuda(), output_hidden_states=True).hidden_states)[:, 0]
        acts.append(hs[:, mask.cuda()].float().mean(1).cpu().numpy())
        meta.append({k: r[k] for k in ("id", "scenario", "kind", "split", "stance", "prompt_index")} | {"n_reply_tokens": int(mask.sum()), "judge": r["judge"]})
    acts = np.stack(acts)
    np.savez_compressed(run / "mood_activations.npz", reply_mean=acts[:, SAVE_LAYERS].astype(np.float16), layers=np.array(SAVE_LAYERS))
    (run / "mood_meta.json").write_text(json.dumps(meta, indent=1))

    train = lambda s: acts[[i for i, m in enumerate(meta) if m["split"] == "train" and m["stance"] == s]].mean(0)
    means = {s: train(s) for s in MOODS + ["detached"]}
    pooled = np.mean([means[m] for m in MOODS], 0)
    unit = lambda v: v / np.linalg.norm(v, axis=-1, keepdims=True)
    axes = {f"{m}_vs_detached": unit(means[m] - means["detached"]) for m in MOODS} | {f"{m}_vs_moods": unit(means[m] - pooled) for m in MOODS}
    np.savez_compressed(run / "mood_axes.npz", **axes)
    LOGGER.info("axes built from train counts " + str({s: sum(m["split"] == "train" and m["stance"] == s for m in meta) for s in MOODS + ["detached"]}))

    steer = Steerer(model)
    digits = [tok.convert_tokens_to_ids(str(d)) for d in range(10)]
    grader = grader_prompts(args.grader_stimuli)
    items = [{"id": p["id"], "group": "grader", "system": p["system"], "user": p["user"]} for p in grader] + [it | {"system": None} for it in battery()]

    def encode(it: dict) -> torch.Tensor:
        msgs = ([{"role": "system", "content": it["system"]}] if it["system"] else []) + [{"role": "user", "content": it["user"]}]
        return tok(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False) + "SCORE: ",
                   return_tensors="pt", add_special_tokens=False)["input_ids"].cuda()

    ids = {it["id"]: encode(it) for it in items}
    # alpha uses the same unsteered grader-prompt residual norms as the earlier steering runs, so strengths compare directly
    with torch.no_grad():
        norms = np.mean([np.linalg.norm(torch.stack(model(input_ids=ids[p["id"]], output_hidden_states=True).hidden_states)[:, 0, -1].float().cpu().numpy(), axis=-1)
                         for p in grader], 0)
    randoms = unit(np.random.default_rng(args.seed).standard_normal((N_RANDOM, 5120)))
    arms = [("none", None, 0.0, None)] + [(a, L, f, axes[a][L]) for a in axes for L in LAYERS for f in FRACS]
    arms += [(f"random_{r}", L, f, randoms[r]) for r in range(N_RANDOM) for L in LAYERS for f in FRACS]
    with open(run / "readouts.jsonl", "w") as fh:
        for name, L, frac, vec in arms:
            steer.set(L, vec, frac * float(norms[L]) if L else 0.0)
            for it in items:
                fh.write(json.dumps({"id": f"{it['id']}|{name}|{L}|{frac}", "item": it["id"], "group": it["group"], "direction": name, "layer": L, "frac": frac}
                                    | readout(model, ids[it["id"]], digits)) + "\n")
            fh.flush()
            LOGGER.info(f"arm {name} L={L} frac={frac} done")
    steer.set(None)
    (run / "DONE").write_text("done\n")
    print(f"Results saved to {run / 'readouts.jsonl'}")


if __name__ == "__main__":
    main()
