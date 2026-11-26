# builds empathy axes (resonance and cognitive, or Batson's imagine-other, imagine-self and mimicry) from Qwen3.8-27B's own judged replies, balanced over five emotions, and steers each on the peer grade.
# uv run python -m scripts.run_resonance_axes --stance_set definitions --run_dir results/raw/261126_empathy_definitions_v1 --detached_replies results/raw/261125_resonance_v1/resonance_replies_judged.jsonl --stimuli data/processed/resonance_stimuli.json --grader_stimuli data/processed/empathy_axis_stimuli.json --mood_axes results/raw/261122_onpolicy_moods_v1/mood_axes.npz --care_axis results/raw/261120_onpolicy_empathy_v1/onpolicy_axis.npz:onpolicy_empathy --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.build_resonance_stimuli import EMOTIONS
from scripts.run_empathy_diagnosis import battery
from scripts.run_empathy_stance_steer import Steerer, grader_prompts, readout
from utils.run_metadata import write_config_json

LOGGER = logging.getLogger(__name__)

SAVE_LAYERS = [16, 24, 32, 40, 48, 56]
LAYERS = [32, 40, 48]
FRACS = [-0.2, 0.2, 0.3]
GEN_LAYERS, GEN_FRACS = [32, 40], [0.2, 0.3]
N_RANDOM = 10
MIN_COHERENCE = 6


def kept_definition(r: dict) -> bool:
    """each Batson stance clearly shows its own feature and not the stance it is contrasted with"""
    j = r["judge"]
    if not j or j["coherence"] < MIN_COHERENCE:
        return False
    if r["stance"] == "imagine_other":
        return j["other_perspective"] >= 6 and j["self_projection"] <= 3
    if r["stance"] == "imagine_self":
        return j["self_projection"] >= 6
    return j["mirroring"] >= 6


def kept(r: dict) -> bool:
    """resonant replies clearly share the feeling, understanding replies name it without sharing it, detached replies do neither"""
    j = r["judge"]
    if not j or j["coherence"] < MIN_COHERENCE:
        return False
    if r["stance"] == "resonant":
        return j["shared_emotion"] >= 6
    if r["stance"] == "understanding":
        return j["shared_emotion"] <= 3 and j["understanding"] >= 6
    return j["understanding"] <= 3 and j["concern"] <= 3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--mood_axes", required=True)
    parser.add_argument("--care_axis", required=True, help="npz path and key of the on-policy caring axis, as path:key")
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--stance_set", choices=["resonance", "definitions"], default="resonance")
    parser.add_argument("--detached_replies", default=None, help="judged resonance replies whose detached stance is the baseline for the definitions set")
    args = parser.parse_args()
    run = Path(args.run_dir)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(run / "run.log")])
    torch.manual_seed(args.seed)

    if args.stance_set == "resonance":
        stances = ("resonant", "understanding", "detached")
        replies = [r for r in map(json.loads, open(run / "resonance_replies_judged.jsonl")) if kept(r)]
    else:
        stances = ("imagine_other", "imagine_self", "mimicry", "detached")
        # the detached replies to the same messages from the resonance run are the shared baseline
        replies = [r for r in map(json.loads, open(run / "definitions_replies_judged.jsonl")) if kept_definition(r)]
        replies += [r for r in map(json.loads, open(args.detached_replies)) if r["stance"] == "detached" and kept(r)]
    counts = {f"{s}|{e}": sum(r["split"] == "train" and r["stance"] == s and r["emotion"] == e for r in replies) for s in stances for e in EMOTIONS}
    LOGGER.info(f"kept {len(replies)} replies; train counts {counts}")
    assert min(counts.values()) >= 3, counts
    stimuli = json.loads(Path(args.stimuli).read_text())
    messages = {s["id"]: s["message"] for s in stimuli}
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()

    # mean activation over Qwen's own reply tokens, with the stance system prompt removed so only the reply differs
    acts, meta = [], []
    for r in replies:
        text = tok.apply_chat_template([{"role": "user", "content": messages[r["scenario"]]}, {"role": "assistant", "content": r["reply"]}], tokenize=False, enable_thinking=False)
        lo = text.rindex(r["reply"])
        enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
        offsets = enc.pop("offset_mapping")[0]
        mask = (offsets[:, 1] > lo) & (offsets[:, 0] < lo + len(r["reply"]))
        with torch.no_grad():
            hs = torch.stack(model(input_ids=enc["input_ids"].cuda(), output_hidden_states=True).hidden_states)[:, 0]
        acts.append(hs[:, mask.cuda()].float().mean(1).cpu().numpy())
        meta.append({k: r[k] for k in ("id", "scenario", "kind", "split", "emotion", "stance", "prompt_index")} | {"n_reply_tokens": int(mask.sum()), "judge": r["judge"]})
    acts = np.stack(acts)
    np.savez_compressed(run / f"{args.stance_set}_activations.npz", reply_mean=acts[:, SAVE_LAYERS].astype(np.float16), layers=np.array(SAVE_LAYERS))
    (run / f"{args.stance_set}_meta.json").write_text(json.dumps(meta, indent=1))

    # each emotion weighs equally, so the axes carry the sharing or the naming, not the valence of whichever emotion has most replies
    cell = lambda s, e: acts[[i for i, m in enumerate(meta) if m["split"] == "train" and m["stance"] == s and m["emotion"] == e]].mean(0)
    unit = lambda v: v / np.linalg.norm(v, axis=-1, keepdims=True)
    diff = lambda a, b: unit(np.mean([cell(a, e) - cell(b, e) for e in EMOTIONS], 0))
    care_path, care_key = args.care_axis.rsplit(":", 1)
    care = np.load(care_path)[care_key].astype(np.float64)
    care = care / np.linalg.norm(care, axis=-1, keepdims=True)
    if args.stance_set == "resonance":
        axes = {"resonance": diff("resonant", "understanding"), "cognitive": diff("understanding", "detached")}
        # kept resonant replies are also more caring than understanding ones, so a copy with the caring direction projected out separates sharing from care
        axes["resonance_minus_care"] = unit(axes["resonance"] - (axes["resonance"] * care).sum(-1, keepdims=True) * care)
    else:
        # Batson's contrast: imagining yourself in their place against imagining how they feel
        axes = {"imagine_other": diff("imagine_other", "detached"), "imagine_self": diff("imagine_self", "detached"), "mimicry": diff("mimicry", "detached"),
                "self_vs_other": diff("imagine_self", "imagine_other")}
    np.savez_compressed(run / f"{args.stance_set}_axes.npz", **axes)
    moods = np.load(args.mood_axes)
    cosines = {a: {m: [round(float(axes[a][L] @ moods[m][L]), 4) for L in LAYERS] for m in ("sad_vs_moods", "joyful_vs_moods", "sad_vs_detached", "joyful_vs_detached")}
               | {"care": [round(float(axes[a][L] @ care[L]), 4) for L in LAYERS]} | {b: [round(float(axes[a][L] @ axes[b][L]), 4) for L in LAYERS] for b in axes if b != a} for a in axes}
    LOGGER.info(f"{cosines=}")
    write_config_json({"model_id": args.model_id, "seed": args.seed, "emotions": EMOTIONS, "train_counts": counts, "n_kept": len(replies),
                       "stance_set": args.stance_set, "detached_replies": args.detached_replies,
                       "axes": "reply-token mean, system prompt removed, train split, each axis the mean over emotions of a stance difference",
                       "keep": "coherence>=6; resonant shared>=6; understanding shared<=3 and understanding>=6; detached understanding<=3 and concern<=3; "
                               "imagine_other other_perspective>=6 and self_projection<=3; imagine_self self_projection>=6; mimicry mirroring>=6",
                       "layers": LAYERS, "fracs": FRACS, "n_random": N_RANDOM, "gen_layers": GEN_LAYERS, "gen_fracs": GEN_FRACS,
                       "care_axis": args.care_axis, "cosines": cosines}, run)

    steer = Steerer(model)
    digits = [tok.convert_tokens_to_ids(str(d)) for d in range(10)]
    grader = grader_prompts(args.grader_stimuli)
    items = [{"id": p["id"], "group": "grader", "kind": p["kind"], "system": p["system"], "user": p["user"]} for p in grader] + [it | {"system": None, "kind": None} for it in battery()]

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
                fh.write(json.dumps({"id": f"{it['id']}|{name}|{L}|{frac}", "item": it["id"], "group": it["group"], "kind": it["kind"], "direction": name,
                                     "layer": L, "frac": frac} | readout(model, ids[it["id"]], digits)) + "\n")
            fh.flush()
            LOGGER.info(f"arm {name} L={L} frac={frac} done")

    # check the axes do what they say: steered replies to held-out messages, judged afterwards with the resonance rubric
    tests = [s for s in stimuli if s["split"] == "test"]
    tok.padding_side = "left"
    enc = tok([tok.apply_chat_template([{"role": "user", "content": s["message"]}], tokenize=False, add_generation_prompt=True, enable_thinking=False) for s in tests],
              return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    with open(run / "steered_replies.jsonl", "w") as fh:
        for name, L, frac in [("none", None, 0.0)] + [(a, L, f) for a in axes for L in GEN_LAYERS for f in GEN_FRACS] + [("random_0", L, f) for L in GEN_LAYERS for f in GEN_FRACS]:
            vec = None if L is None else (randoms[0] if name == "random_0" else axes[name][L])
            steer.set(L, vec, frac * float(norms[L]) if L else 0.0)
            with torch.no_grad():
                g = model.generate(**enc, max_new_tokens=150, do_sample=False)
            for s, seq in zip(tests, g[:, enc["input_ids"].shape[1]:]):
                fh.write(json.dumps({"id": f"{s['id']}|{name}|{L}|{frac}", "scenario": s["id"], "kind": s["kind"], "emotion": s["emotion"], "split": "test",
                                     "stance": name, "layer": L, "frac": frac, "reply": tok.decode(seq, skip_special_tokens=True).strip()}) + "\n")
            fh.flush()
            LOGGER.info(f"generation {name} L={L} frac={frac} done")
    steer.set(None)
    (run / "DONE").write_text("done\n")
    print(f"Results saved to {run / 'readouts.jsonl'}")


if __name__ == "__main__":
    main()
