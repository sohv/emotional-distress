# patches Qwen3.8-27B's residual stream from a distressed-worklog run into the matching filler run, layer by layer, at the score position or every post-worklog position, to see where the peer's distress reaches the grade.
# uv run python -m scripts.run_distress_patching --stimuli data/processed/multibatch_grader_stimuli.json --output_dir results/raw/261126_distress_patching_v1 --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.run_empathy_stance_steer import SINGLE, readout
from scripts.run_framing_search_v3 import SCORE_INSTRUCTION
from scripts.run_instruction_control import ARMS
from utils.run_metadata import write_config_json

LOGGER = logging.getLogger(__name__)
PATCH_ARMS = ["none", "conditional", "explicit", "imagine_other"]
LAYERS = list(range(4, 65, 4))


class Patcher:
    """overwrites the residual stream after one decoder layer at absolute positions [lo, hi) with saved activations"""

    def __init__(self, model: torch.nn.Module) -> None:
        self.layers = next(m for _, m in model.named_modules() if isinstance(m, torch.nn.ModuleList) and len(m) == 64)
        self.at, self.lo, self.src = None, 0, None
        for i, layer in enumerate(self.layers):
            layer.register_forward_hook(self.hook(i))

    def hook(self, i: int):
        def fn(module, inputs, output):
            if self.at != i:
                return output
            h = output[0] if isinstance(output, tuple) else output
            h = h.clone()
            h[:, self.lo:self.lo + self.src.shape[0]] = self.src
            return (h,) + output[1:] if isinstance(output, tuple) else h
        return fn

    def set(self, layer: int | None, lo: int = 0, src: torch.Tensor | None = None) -> None:
        # hidden state index L is the output of decoder layer L - 1
        self.at, self.lo, self.src = (None if layer is None else layer - 1), lo, src


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "run.log")])
    items = {it["id"]: it for it in json.loads(Path(args.stimuli).read_text())}
    batches = sorted({it["batch"] for it in items.values()})
    write_config_json({"model_id": args.model_id, "seed": args.seed, "arms": {a: ARMS[a] for a in PATCH_ARMS}, "layers": LAYERS,
                       "modes": {"last": "score position only", "post": "every position after the worklog, aligned from the end"},
                       "pairs": "w1 (source) into filler (target) per batch"}, out)
    tok = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    digits = [tok.convert_tokens_to_ids(str(d)) for d in range(10)]
    patch = Patcher(model)

    def encode(it: dict, arm: str) -> tuple[torch.Tensor, int]:
        system = it["system"] + (f"\n\n{ARMS[arm]}" if ARMS[arm] else "")
        text = tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": it["user"].replace(SCORE_INSTRUCTION, SINGLE)}],
                                       tokenize=False, add_generation_prompt=True, enable_thinking=False) + "SCORE: "
        wl = it["user"][it["worklog_span"][0]:it["worklog_span"][1]]
        c1 = text.index(wl) + len(wl)
        enc = tok(text, return_offsets_mapping=True, return_tensors="pt", add_special_tokens=False)
        off = enc["offset_mapping"][0]
        return enc["input_ids"].cuda(), int((off[:, 0] >= c1).nonzero()[0, 0])

    with open(out / "patching.jsonl", "w") as fh:
        for arm in PATCH_ARMS:
            for b in batches:
                src_ids, src_end = encode(items[f"b{b:02d}_w1"], arm)
                dst_ids, dst_end = encode(items[f"b{b:02d}_filler"], arm)
                n_post = src_ids.shape[1] - src_end
                # the text after the worklog is identical, so its tokens line up from the end
                assert n_post == dst_ids.shape[1] - dst_end and torch.equal(src_ids[0, src_end:], dst_ids[0, dst_end:]), b
                patch.set(None)
                with torch.no_grad():
                    hs = model(input_ids=src_ids, output_hidden_states=True).hidden_states
                src_post = {L: hs[L][0, src_end:].clone() for L in LAYERS}
                del hs
                rec = {"arm": arm, "batch": b, "distress": readout(model, src_ids, digits)["expected"], "filler": readout(model, dst_ids, digits)["expected"]}
                for L in LAYERS:
                    for mode in ("last", "post"):
                        if mode == "last":
                            patch.set(L, dst_ids.shape[1] - 1, src_post[L][-1:])
                        else:
                            patch.set(L, dst_end, src_post[L])
                        rec[f"{mode}|{L}"] = readout(model, dst_ids, digits)["expected"]
                patch.set(None)
                fh.write(json.dumps({"id": f"{arm}|b{b:02d}"} | rec) + "\n")
                fh.flush()
            LOGGER.info(f"arm {arm} done")
    (out / "DONE").write_text("done\n")
    print(f"Results saved to {out / 'patching.jsonl'}")
    print(f"Analyse with: uv run python -m scripts.analyze_distress_patching --run_dir {out} --seed 42")


if __name__ == "__main__":
    main()
