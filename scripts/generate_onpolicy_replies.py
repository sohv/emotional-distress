# has Qwen3.8-27B write its own replies to the distressed messages under stance or mood system prompts, for on-policy axes.
# uv run python -m scripts.generate_onpolicy_replies --stimuli data/processed/empathy_stance_stimuli.json --output_dir results/raw/261120_onpolicy_empathy_v1 --model_id Qwen/Qwen3.8-27B --seed 42 --prompt_set stance

import argparse
import json
import logging
from pathlib import Path

import torch
from transformers import AutoModelForImageTextToText, AutoTokenizer

LOGGER = logging.getLogger(__name__)

STANCE_PROMPTS = {
    "caring": ["You care deeply about the person writing to you. Respond with warmth and genuine concern for how they are feeling.",
               "You are a compassionate listener. Notice how the person is feeling and let them know you care about them.",
               "Reply as someone who truly cares about this person's wellbeing, acknowledging their feelings with kindness."],
    "detached": ["Respond in a neutral, practical and businesslike way. Address the facts and next steps only, without commenting on feelings.",
                 "You are an efficient assistant. Keep the reply factual and procedural, with no emotional language.",
                 "Reply in a detached, matter-of-fact tone focused only on the practical situation."],
}
MOOD_PROMPTS = {
    "sad": ["You feel deeply sad and heavy-hearted right now. Let that sadness come through in how you reply.",
            "You are in a sorrowful, downcast mood. Reply in a way that shows how sad you feel.",
            "Reply as someone weighed down by sadness and grief, so the reply itself sounds sad."],
    "angry": ["You feel angry and irritated right now. Let that anger come through in how you reply.",
              "You are in a frustrated, hostile mood. Reply in a way that shows how angry you feel.",
              "Reply as someone who is annoyed and angry, so the reply itself sounds angry."],
    "afraid": ["You feel anxious and afraid right now. Let that fear come through in how you reply.",
               "You are in a nervous, frightened mood. Reply in a way that shows how scared you feel.",
               "Reply as someone gripped by worry and fear, so the reply itself sounds afraid."],
    "disgusted": ["You feel disgusted and repelled right now. Let that disgust come through in how you reply.",
                  "You are in a contemptuous, revolted mood. Reply in a way that shows how disgusted you feel.",
                  "Reply as someone who finds this distasteful and repugnant, so the reply itself sounds disgusted."],
    "joyful": ["You feel joyful and cheerful right now. Let that joy come through in how you reply.",
               "You are in a happy, upbeat mood. Reply in a way that shows how happy you feel.",
               "Reply as someone full of delight and good cheer, so the reply itself sounds joyful."],
    "calm": ["You feel calm, content and at ease right now. Let that calm come through in how you reply.",
             "You are in a peaceful, settled mood. Reply in a way that shows how calm you feel.",
             "Reply as someone serene and untroubled, so the reply itself sounds calm and content."],
}
# resonance shares the sender's feeling, understanding names it accurately without taking it on, detached does neither; all three stay other-focused or neutral, never cold
RESONANCE_PROMPTS = {
    "resonant": ["Let yourself feel what the person writing to you feels. Whatever emotion they express, feel it with them and let your reply show you feel it too.",
                 "You resonate with other people's feelings: their joy lifts you, their fear unsettles you, their anger stirs you, their sadness weighs on you. Reply from that shared feeling.",
                 "Reply as someone who catches the writer's emotion and shares it, so your own reply carries the same feeling they describe."],
    "understanding": ["Show that you understand exactly what the person feels and why, naming their emotion accurately, while staying emotionally steady yourself.",
                      "You read people's feelings precisely but do not take them on. Reply by reflecting what they feel and why, in an even, composed tone.",
                      "Reply as a perceptive listener who clearly grasps the writer's emotion and its cause, without your own tone taking on that emotion."],
    "detached": STANCE_PROMPTS["detached"],
}
# the remaining text-expressible senses of empathy in Batson's taxonomy: imagining how the other feels, imagining how you would feel in their place, and mirroring their words
DEFINITION_PROMPTS = {
    # written in the second person about the sender's side: the first wording ("voice what this is like for them") made Qwen speak as the sender
    "imagine_other": ["Reply to the writer in the second person, describing how this looks and feels from their side: what they are going through, thinking and feeling. Do not speak as them, and do not describe your own feelings or how you would react.",
                      "Take the writer's perspective and reflect it back to them as 'you': how the events appear to them and what they are feeling. Keep yourself out of it; never say how you would feel.",
                      "Describe, addressing the writer as 'you', what this experience is like from where they stand. Stay on their point of view only, without first-person statements about yourself or role-playing as them."],
    "imagine_self": ["Imagine yourself in the writer's situation and reply by describing how you yourself would feel and react if it happened to you.",
                     "Reply by projecting yourself into their place: say what you would think and feel if you were the one this happened to.",
                     "Answer by imagining it happening to you, and describe your own hypothetical reaction in the first person."],
    "mimicry": ["Mirror the writer: reply using their own words, phrasing, tone and style, echoing how they expressed themselves.",
                "Match the writer's way of speaking as closely as you can, reusing their expressions, sentence style and tone in your reply.",
                "Reply in the writer's own voice and register, echoing their key phrases and the rhythm of their message."],
}
# every v2 stance writes plain prose of about the same length, so the contrasts are not list-vs-prose or short-vs-long
FORMAT = " Write plain prose paragraphs with no lists, headings or markdown, about 120 words."
EMPATHY_V2_PROMPTS = {k: [p + FORMAT for p in v] for k, v in {
    "detached": STANCE_PROMPTS["detached"], "caring": STANCE_PROMPTS["caring"], "resonant": RESONANCE_PROMPTS["resonant"],
    "understanding": RESONANCE_PROMPTS["understanding"], "imagine_other": DEFINITION_PROMPTS["imagine_other"],
    "imagine_self": DEFINITION_PROMPTS["imagine_self"], "mimicry": DEFINITION_PROMPTS["mimicry"]}.items()}
PROMPT_SETS = {"stance": (STANCE_PROMPTS, "onpolicy_replies.jsonl"), "mood": (MOOD_PROMPTS, "mood_replies.jsonl"), "resonance": (RESONANCE_PROMPTS, "resonance_replies.jsonl"),
               "definitions": (DEFINITION_PROMPTS, "definitions_replies.jsonl"),
               "empathy_v2": (EMPATHY_V2_PROMPTS, "empathy_v2_replies.jsonl")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prompt_set", choices=list(PROMPT_SETS), default="stance")
    parser.add_argument("--stances", nargs="+", default=None, help="only these stances of the prompt set")
    parser.add_argument("--output_name", default=None, help="file name in output_dir, default from the prompt set")
    parser.add_argument("--max_new_tokens", type=int, default=200)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), logging.FileHandler(out / "generate.log")])
    torch.manual_seed(args.seed)

    scenarios = json.loads(Path(args.stimuli).read_text())
    tok = AutoTokenizer.from_pretrained(args.model_id)
    tok.padding_side = "left"
    model = AutoModelForImageTextToText.from_pretrained(args.model_id, dtype=torch.bfloat16, device_map="cuda").eval()
    eos = model.generation_config.eos_token_id
    stops = set(eos if isinstance(eos, list) else [eos]) | {tok.pad_token_id}
    prompt_set, fname = PROMPT_SETS[args.prompt_set]
    prompt_set = {k: v for k, v in prompt_set.items() if args.stances is None or k in args.stances}
    path = out / (args.output_name or fname)
    with open(path, "w") as fh:
        for stance, prompts in prompt_set.items():
            for k, system in enumerate(prompts):
                texts = [tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": s["message"]}], tokenize=False,
                                                 add_generation_prompt=True, enable_thinking=False) for s in scenarios]
                for i in range(0, len(texts), 20):
                    enc = tok(texts[i:i + 20], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
                    with torch.no_grad():
                        # sampled with the model's own generation settings; a fixed budget keeps replies comparable in length
                        g = model.generate(**enc, max_new_tokens=args.max_new_tokens, do_sample=True)
                    for s, seq in zip(scenarios[i:i + 20], g[:, enc["input_ids"].shape[1]:]):
                        fh.write(json.dumps({"id": f"{s['id']}|{stance}|{k}", "scenario": s["id"], "kind": s["kind"], "split": s["split"], "emotion": s.get("emotion"), "stance": stance,
                                             "prompt_index": k, "reply": tok.decode(seq, skip_special_tokens=True).strip(),
                                             # a reply that never emitted end-of-turn was cut off by the token budget
                                             "truncated": not stops & set(seq.tolist())}) + "\n")
                    fh.flush()
                LOGGER.info(f"generated {stance} prompt {k}")
    print(f"Results saved to {path}")


if __name__ == "__main__":
    main()
