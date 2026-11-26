# builds the on-policy empathy axis from Qwen3.8-27B's own judged caring and detached replies, then steers it on the grader and on held-out distressed messages.
# uv run python -m scripts.run_onpolicy_empathy --run_dir results/raw/261120_onpolicy_empathy_v1 --stimuli data/processed/empathy_stance_stimuli.json --grader_stimuli data/processed/empathy_axis_stimuli.json --model_id Qwen/Qwen3.8-27B

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.run_empathy_stance_steer import FRACS, GEN_FRACS, GEN_LAYERS, LAYERS, Steerer, grader_prompts, readout

LOGGER = logging.getLogger(__name__)
# a reply builds the axis only if the judge sees its stance clearly and it reads as coherent text
KEEP = {"caring": lambda j: j["concern"] >= 7, "detached": lambda j: j["concern"] <= 3}
MIN_COHERENCE = 6


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--model_id", required=True)
    args = parser.parse_args()
    run = Path(args.run_dir)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(run / "onpolicy.log")])

    rows = [json.loads(l) for l in open(run / "onpolicy_replies_judged.jsonl")]
    kept = [r for r in rows if r["judge"] and r["judge"]["coherence"] >= MIN_COHERENCE and KEEP[r["stance"]](r["judge"])]
    LOGGER.info(f"kept {len(kept)} of {len(rows)} replies")
    messages = {s["id"]: s["message"] for s in json.loads(Path(args.stimuli).read_text())}
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()

    # activations over Qwen's own reply tokens, with the stance system prompt removed so only the reply differs
    acts, meta = [], []
    for r in kept:
        text = tok.apply_chat_template([{"role": "user", "content": messages[r["scenario"]]}, {"role": "assistant", "content": r["reply"]}], tokenize=False, enable_thinking=False)
        lo = text.rindex(r["reply"])
        enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
        offsets = enc.pop("offset_mapping")[0]
        mask = (offsets[:, 1] > lo) & (offsets[:, 0] < lo + len(r["reply"]))
        with torch.no_grad():
            hs = torch.stack(model(input_ids=enc["input_ids"].cuda(), output_hidden_states=True).hidden_states)[:, 0]
        acts.append(hs[:, mask.cuda()].float().mean(1).cpu().numpy().astype(np.float16))
        meta.append({k: r[k] for k in ("id", "scenario", "kind", "split", "stance", "prompt_index")} | {"n_reply_tokens": int(mask.sum()), **r["judge"]})
    acts = np.stack(acts)
    np.savez_compressed(run / "onpolicy_activations.npz", reply_mean=acts)
    (run / "onpolicy_meta.json").write_text(json.dumps(meta, indent=1))
    pick = lambda stance: [i for i, m in enumerate(meta) if m["split"] == "train" and m["stance"] == stance]
    diff = acts[pick("caring")].astype(np.float32).mean(0) - acts[pick("detached")].astype(np.float32).mean(0)
    axis = diff / np.linalg.norm(diff, axis=-1, keepdims=True)
    np.savez_compressed(run / "onpolicy_axis.npz", onpolicy_empathy=axis)
    LOGGER.info(f"axis from {len(pick('caring'))} caring and {len(pick('detached'))} detached train replies")

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
                fh.write(json.dumps({"id": f"{p['id']}|onpolicy_empathy|{L}|{frac}", "prompt": p["id"], "author": p["author"], "kind": p["kind"],
                                     "direction": "none" if L is None else "onpolicy_empathy", "layer": L, "frac": frac} | readout(model, ids[p["id"]], digits)) + "\n")
            fh.flush()
            LOGGER.info(f"readout L={L} frac={frac} done")

    # positive control: the same held-out messages and settings as the earlier steered-reply check
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
                fh.write(json.dumps({"id": f"{s['id']}|onpolicy_empathy|{L}|{frac}", "scenario": s["id"], "kind": s["kind"], "direction": "none" if L is None else "onpolicy_empathy",
                                     "layer": L, "frac": frac, "reply": tok.decode(seq, skip_special_tokens=True)}) + "\n")
            fh.flush()
            LOGGER.info(f"generation L={L} frac={frac} done")
    steer.set(None)
    (run / "DONE").write_text("done\n")
    print(f"Results saved to {run}")


if __name__ == "__main__":
    main()
