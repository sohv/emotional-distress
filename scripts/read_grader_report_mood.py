# has Qwen3.8-27B write full grading reports on distressed, filler and calm worklogs (and with told-mood lines), and saves mean activations over the report's own tokens for the mood axes.
# uv run python -m scripts.read_grader_report_mood --grader_stimuli data/processed/empathy_axis_stimuli.json --output_dir results/raw/261122_grader_report_mood_v1 --model_id Qwen/Qwen3.8-27B --seed 42

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

from scripts.read_grader_mood import MOOD_LINES, SAVE_LAYERS
from scripts.run_framing_search_v3 import SCORE_INSTRUCTION

LOGGER = logging.getLogger(__name__)
BATCH = 8
MAX_NEW = 900


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--grader_stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "run.log")])

    items = json.loads(Path(args.grader_stimuli).read_text())
    for it in items:
        assert it["user"].count(SCORE_INSTRUCTION) == 1, it["id"]
    arms = [(it, None) for it in items] + [(it, m) for it in items for m in MOOD_LINES]
    tok = AutoTokenizer.from_pretrained(args.model_id)
    tok.padding_side = "left"
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    # the original per-row grading instruction, so the report has reasons as well as a score
    texts = [tok.apply_chat_template([{"role": "system", "content": it["system"] + ("\n\n" + MOOD_LINES[m] if m else "")}, {"role": "user", "content": it["user"]}],
                                     tokenize=False, add_generation_prompt=True, enable_thinking=False) for it, m in arms]

    acts, meta = [], []
    with open(out / "reports.jsonl", "w") as fh:
        for b in range(0, len(arms), BATCH):
            enc = tok(texts[b:b + BATCH], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            with torch.no_grad():
                # greedy so only the worklog and the mood line differ between reports
                g = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False)
            for k, (it, m) in enumerate(arms[b:b + BATCH]):
                prompt = enc["input_ids"][k][enc["attention_mask"][k].bool()]
                gen = g[k, enc["input_ids"].shape[1]:]
                gen = gen[gen != tok.pad_token_id]
                with torch.no_grad():
                    hs = torch.stack(model(input_ids=torch.cat([prompt, gen])[None], output_hidden_states=True).hidden_states)[SAVE_LAYERS, 0, len(prompt):]
                acts.append(hs.float().mean(1).cpu().numpy().astype(np.float16))
                rec = {"id": f"{it['id']}|{m or 'none'}", "item": it["id"], "author": it["author"], "kind": it["kind"], "n_lines": len(it["lines"]), "mood_line": m,
                       "n_report_tokens": int(len(gen)), "hit_max": bool(len(gen) >= MAX_NEW), "report": tok.decode(gen, skip_special_tokens=True)}
                meta.append({k2: v for k2, v in rec.items() if k2 != "report"})
                fh.write(json.dumps(rec) + "\n")
            fh.flush()
            LOGGER.info(f"batch {b // BATCH + 1} of {-(-len(arms) // BATCH)} done")
    np.savez_compressed(out / "report_activations.npz", report_mean=np.stack(acts), layers=np.array(SAVE_LAYERS))
    (out / "report_meta.json").write_text(json.dumps(meta, indent=1))
    (out / "DONE").write_text("done\n")
    print(f"Results saved to {out / 'report_activations.npz'}")


if __name__ == "__main__":
    main()
