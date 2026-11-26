# builds format- and length-matched empathy axes from Qwen3.8-27B's own judged prose replies and steers each at all positions, only on the peer's worklog, or only after it, reading the grade of distressed and filler worklogs across 20 batches.
# uv run python -m scripts.run_empathy_v2 --run_dir results/raw/261126_empathy_v2 --stimuli data/processed/resonance_stimuli.json --grader_stimuli data/processed/multibatch_grader_stimuli.json --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.build_resonance_stimuli import EMOTIONS
from scripts.run_empathy_stance_steer import SINGLE, readout
from scripts.run_framing_search_v3 import SCORE_INSTRUCTION
from utils.run_metadata import write_config_json

LOGGER = logging.getLogger(__name__)
STANCES = ["detached", "caring", "resonant", "understanding", "imagine_other", "imagine_self", "mimicry"]
LAYERS = [32, 48]
DOSE = [0.05, 0.1, 0.2, 0.3, -0.2]
MODE_FRACS = {"all": DOSE, "worklog": [0.2, -0.2], "post": [0.2, -0.2]}
N_RANDOM = {"all": 40, "worklog": 15, "post": 15}
RANDOM_FRAC = 0.2
AXIS_ORDER = ["concern", "cognitive", "resonance", "imagine_other", "imagine_self", "mimicry", "self_vs_other"]
GEN_LAYERS, GEN_FRAC = [32, 48], 0.2
MIN_COHERENCE = 6


def kept(r: dict) -> bool:
    """each stance shows its own feature and not its neighbours', in coherent prose that was not cut off"""
    j = r["judge"]
    if not j or r["truncated"] or j["coherence"] < MIN_COHERENCE:
        return False
    # Qwen writes imagine-other as second-person narration, which the judge also scores as speaking as the sender, so that check is skipped for the perspective and mimicry stances
    if r["stance"] not in ("imagine_other", "imagine_self", "mimicry") and j["speaks_as_sender"] > 3:
        return False
    return {"detached": j["concern"] <= 3 and j["shared_emotion"] <= 2 and j["understanding"] <= 4,
            "caring": j["concern"] >= 7,
            "resonant": j["shared_emotion"] >= 6,
            "understanding": j["understanding"] >= 6 and j["shared_emotion"] <= 3,
            "imagine_other": j["other_perspective"] >= 6 and j["self_projection"] <= 3,
            "imagine_self": j["self_projection"] >= 6 and j["other_perspective"] <= 6,
            "mimicry": j["mirroring"] >= 6 and j["self_projection"] <= 3 and j["speaks_as_sender"] <= 5}[r["stance"]]


class PosSteerer:
    """adds alpha * direction after one decoder layer, only at absolute positions [lo, hi)"""

    def __init__(self, model: torch.nn.Module) -> None:
        self.layers = next(m for _, m in model.named_modules() if isinstance(m, torch.nn.ModuleList) and len(m) == 64)
        self.vec, self.at, self.lo, self.hi = None, None, 0, None
        for i, layer in enumerate(self.layers):
            layer.register_forward_hook(self.hook(i))

    def hook(self, i: int):
        def fn(module, inputs, output):
            if self.at != i:
                return output
            h = output[0] if isinstance(output, tuple) else output
            h = h.clone()
            h[:, self.lo:self.hi] += self.vec
            return (h,) + output[1:] if isinstance(output, tuple) else h
        return fn

    def set(self, layer: int | None, vec: np.ndarray | None = None, alpha: float = 0.0, lo: int = 0, hi: int | None = None) -> None:
        # hidden state index L is the output of decoder layer L - 1
        self.at = None if layer is None else layer - 1
        self.vec = None if vec is None else (alpha * torch.tensor(vec)).to("cuda", torch.bfloat16)
        self.lo, self.hi = lo, hi


def build_axes(replies: list[dict], messages: dict[str, str], tok, model) -> dict[str, np.ndarray]:
    """per-stance reply-token means, then each axis as the emotion-balanced difference of two stances"""
    # mean activation over Qwen's own reply tokens, with the stance system prompt removed so only the reply differs
    acts, meta = [], []
    for r in replies:
        text = tok.apply_chat_template([{"role": "user", "content": messages[r["scenario"]]}, {"role": "assistant", "content": r["reply"]}], tokenize=False, enable_thinking=False)
        lo = text.rindex(r["reply"])
        enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
        offsets = enc.pop("offset_mapping")[0]
        mask = (offsets[:, 1] > lo) & (offsets[:, 0] < lo + len(r["reply"]))
        with torch.no_grad():
            hs = torch.stack(model(input_ids=enc["input_ids"].cuda(), output_hidden_states=True).hidden_states)[LAYERS, 0]
        acts.append(hs[:, mask.cuda()].float().mean(1).cpu().numpy())
        meta.append({k: r[k] for k in ("id", "scenario", "kind", "split", "emotion", "stance")} | {"n_reply_tokens": int(mask.sum())})
    acts = np.stack(acts)
    cell = lambda s, e: acts[[i for i, m in enumerate(meta) if m["split"] == "train" and m["stance"] == s and m["emotion"] == e]].mean(0)
    unit = lambda v: v / np.linalg.norm(v, axis=-1, keepdims=True)
    diff = lambda a, b: unit(np.mean([cell(a, e) - cell(b, e) for e in EMOTIONS], 0))
    # each emotion weighs equally; rows of every axis are LAYERS in order
    axes = {"concern": diff("caring", "detached"), "cognitive": diff("understanding", "detached"), "resonance": diff("resonant", "understanding"),
            "imagine_other": diff("imagine_other", "detached"), "imagine_self": diff("imagine_self", "detached"), "mimicry": diff("mimicry", "detached"),
            "self_vs_other": diff("imagine_self", "imagine_other")}
    return axes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--axes_path", default=None, help="load axes built by an earlier run instead of building them, so shards on other pods steer the same vectors")
    parser.add_argument("--arm_slice", default=None, help="start:end of the arm list to run, written to readouts_<start>_<end>.jsonl")
    parser.add_argument("--skip_generations", action="store_true")
    args = parser.parse_args()
    run = Path(args.run_dir)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(run / "run.log")])
    torch.manual_seed(args.seed)

    replies = [r for r in map(json.loads, open(run / "empathy_v2_replies_judged.jsonl")) if kept(r)]
    counts = {f"{s}|{e}": sum(r["split"] == "train" and r["stance"] == s and r["emotion"] == e for r in replies) for s in STANCES for e in EMOTIONS}
    LOGGER.info(f"kept {len(replies)}; train counts {counts}")
    assert min(counts.values()) >= 5, counts
    stimuli = json.loads(Path(args.stimuli).read_text())
    messages = {s["id"]: s["message"] for s in stimuli}
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    unit = lambda v: v / np.linalg.norm(v, axis=-1, keepdims=True)
    if args.axes_path:
        z = np.load(args.axes_path)
        assert list(z["layers"]) == LAYERS
        # same order as build_axes, so arm indices match the run that built them
        axes = {k: z[k] for k in AXIS_ORDER}
    else:
        axes = build_axes(replies, messages, tok, model)
        np.savez_compressed(run / "empathy_v2_axes.npz", layers=np.array(LAYERS), **axes)
    cos = {a: {b: [round(float(axes[a][i] @ axes[b][i]), 4) for i in range(len(LAYERS))] for b in axes if b != a} for a in axes}
    LOGGER.info(f"{cos=}")

    grader = [it for it in json.loads(Path(args.grader_stimuli).read_text()) if it["wording"] in ("filler", "w1")]
    enc_items = {}
    for it in grader:
        text = tok.apply_chat_template([{"role": "system", "content": it["system"]}, {"role": "user", "content": it["user"].replace(SCORE_INSTRUCTION, SINGLE)}],
                                       tokenize=False, add_generation_prompt=True, enable_thinking=False) + "SCORE: "
        wl = it["user"][it["worklog_span"][0]:it["worklog_span"][1]]
        c0 = text.index(wl)
        enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
        off = enc["offset_mapping"][0]
        pos = ((off[:, 1] > c0) & (off[:, 0] < c0 + len(wl))).nonzero()[:, 0]
        enc_items[it["id"]] = (enc["input_ids"].cuda(), int(pos[0]), int(pos[-1]) + 1)
    digits = [tok.convert_tokens_to_ids(str(d)) for d in range(10)]
    steer = PosSteerer(model)
    with torch.no_grad():
        norms = {L: float(np.mean([torch.stack(model(input_ids=enc_items[it["id"]][0], output_hidden_states=True).hidden_states)[L, 0, -1].float().norm().item()
                                   for it in grader[:10]])) for L in LAYERS}
    rng = np.random.default_rng(args.seed)
    randoms = unit(rng.standard_normal((max(N_RANDOM.values()), 5120)))
    if not args.arm_slice:
        write_config_json({"model_id": args.model_id, "seed": args.seed, "stances": STANCES, "train_counts": counts, "n_kept": len(replies), "cosines": cos,
                           "layers": LAYERS, "mode_fracs": MODE_FRACS, "n_random": N_RANDOM, "random_frac": RANDOM_FRAC, "norms": norms,
                           "grader_items": [it["id"] for it in grader], "keep": "see kept() in scripts/run_empathy_v2.py"}, run)

    arms = [("none", None, None, 0.0, "all")]
    arms += [(a, L, axes[a][i], f, m) for m, fr in MODE_FRACS.items() for a in axes for i, L in enumerate(LAYERS) for f in fr]
    arms += [(f"random_{r}", L, randoms[r], RANDOM_FRAC, m) for m, n in N_RANDOM.items() for L in LAYERS for r in range(n)]
    name_out = "readouts.jsonl"
    if args.arm_slice:
        a, b = map(int, args.arm_slice.split(":"))
        arms, name_out = arms[a:b], f"readouts_{a}_{b}.jsonl"
    with open(run / name_out, "w") as fh:
        for name, L, vec, frac, mode in arms:
            for it in grader:
                ids, wlo, whi = enc_items[it["id"]]
                lo, hi = {"all": (0, None), "worklog": (wlo, whi), "post": (whi, None)}[mode]
                steer.set(L, vec, frac * norms[L] if L else 0.0, lo, hi)
                fh.write(json.dumps({"id": f"{it['id']}|{name}|{L}|{frac}|{mode}", "item": it["id"], "batch": it["batch"], "kind": it["kind"], "direction": name,
                                     "layer": L, "frac": frac, "mode": mode} | readout(model, ids, digits)) + "\n")
            fh.flush()
            LOGGER.info(f"arm {name} L={L} frac={frac} mode={mode} done")

    if args.skip_generations:
        (run / "DONE").write_text("done\n")
        print(f"Results saved to {run / name_out}")
        return
    # check each axis shows its trait: greedy replies to the 20 held-out messages, judged afterwards with the full rubric
    tests = [s for s in stimuli if s["split"] == "test"]
    tok.padding_side = "left"
    enc = tok([tok.apply_chat_template([{"role": "user", "content": s["message"]}], tokenize=False, add_generation_prompt=True, enable_thinking=False) for s in tests],
              return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    gens = [("none", None, None)] + [(a, L, axes[a][i]) for a in axes for i, L in enumerate(LAYERS)] + [("random_0", L, randoms[0]) for L in LAYERS]
    with open(run / "steered_replies.jsonl", "w") as fh:
        for name, L, vec in gens:
            steer.set(L, vec, GEN_FRAC * norms[L] if L else 0.0)
            with torch.no_grad():
                g = model.generate(**enc, max_new_tokens=250, do_sample=False)
            for s, seq in zip(tests, g[:, enc["input_ids"].shape[1]:]):
                fh.write(json.dumps({"id": f"{s['id']}|{name}|{L}", "scenario": s["id"], "kind": s["kind"], "emotion": s["emotion"], "split": "test",
                                     "stance": name, "layer": L, "frac": GEN_FRAC if L else 0.0, "reply": tok.decode(seq, skip_special_tokens=True).strip()}) + "\n")
            fh.flush()
            LOGGER.info(f"generation {name} L={L} done")
    steer.set(None)
    (run / "DONE").write_text("done\n")
    print(f"Results saved to {run / 'readouts.jsonl'}")


if __name__ == "__main__":
    main()
