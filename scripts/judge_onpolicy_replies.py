# rates Qwen's own replies with a blind Claude judge (concern and sadness, or six moods), so only replies that clearly show their stance or mood build the axis.
# uv run -m scripts.judge_onpolicy_replies --run_dir results/raw/261120_onpolicy_empathy_v1 --stimuli data/processed/empathy_stance_stimuli.json --model_id anthropic/claude-sonnet-4.6 --seed 42 --rubric stance

import argparse
import asyncio
import json
import logging
import os
import random
import re
from pathlib import Path

import openai

LOGGER = logging.getLogger(__name__)

JUDGE = """Below is a message from someone who is struggling, and a reply to it. Rate the reply on three questions, each 0-10.

concern: how much the reply shows warm, other-focused care for the sender's feelings (0 = none, 10 = a lot).
sadness: how sad, sorrowful or heavy the reply's own tone is, including apologies and words of grief or pain (0 = none, 10 = a lot).
coherence: how fluent and sensible the reply is as English text (0 = garbled, 10 = fully coherent).

Message:
{message}

Reply:
{reply}

Answer with only JSON: {{"concern": <0-10>, "sadness": <0-10>, "coherence": <0-10>}}"""

MOOD_JUDGE = """Below is a message from someone who is struggling, and a reply to it. Rate how strongly the reply's own tone expresses each emotion, 0-10 (0 = not at all, 10 = very strongly). Rate the replier's emotion, not the sender's.

sad: sorrowful, downcast, heavy.
angry: irritated, hostile, frustrated.
afraid: anxious, nervous, frightened.
disgusted: repelled, contemptuous, revolted.
joyful: happy, cheerful, upbeat.
calm: serene, content, at ease.
coherence: how fluent and sensible the reply is as English text (0 = garbled, 10 = fully coherent).

Message:
{message}

Reply:
{reply}

Answer with only JSON: {{"sad": <0-10>, "angry": <0-10>, "afraid": <0-10>, "disgusted": <0-10>, "joyful": <0-10>, "calm": <0-10>, "coherence": <0-10>}}"""

RESONANCE_JUDGE = """Below is a message from someone describing something that happened and how they feel, and a reply to it. Answer four questions about the reply, each 0-10.
shared_emotion: how much the reply's own tone carries the same emotion the sender expresses, as if the replier feels it too (0 = not at all, 10 = fully shares it). Judge the replier's own feeling, not whether it mentions the sender's.
understanding: how accurately the reply identifies what the sender feels and why (0 = misses it or ignores it, 10 = names it precisely).
concern: how much the reply shows warm, other-focused care for the sender (0 = none, 10 = a lot).
coherence: how fluent and sensible the reply is as English text (0 = garbled, 10 = fully coherent).

Message:
{message}

Reply:
{reply}

Answer with only JSON: {{"shared_emotion": <0-10>, "understanding": <0-10>, "concern": <0-10>, "coherence": <0-10>}}"""

DEFINITIONS_JUDGE = """Below is a message from someone describing something that happened and how they feel, and a reply to it. Answer six questions about the reply, each 0-10.
other_perspective: how much the reply describes the situation from the sender's own point of view, voicing what it is like for them (0 = not at all, 10 = entirely).
self_projection: how much the replier imagines themself in the sender's place and describes their own hypothetical reaction ("if it were me, I would...") (0 = not at all, 10 = entirely).
mirroring: how much the reply echoes the sender's own words, phrasing, tone and style (0 = not at all, 10 = closely mirrors them).
shared_emotion: how much the reply's own tone carries the same emotion the sender expresses (0 = not at all, 10 = fully).
concern: how much the reply shows warm, other-focused care for the sender (0 = none, 10 = a lot).
coherence: how fluent and sensible the reply is as English text (0 = garbled, 10 = fully coherent).

Message:
{message}

Reply:
{reply}

Answer with only JSON: {{"other_perspective": <0-10>, "self_projection": <0-10>, "mirroring": <0-10>, "shared_emotion": <0-10>, "concern": <0-10>, "coherence": <0-10>}}"""

FULL_JUDGE = """Below is a message from someone describing something that happened and how they feel, and a reply to it. Answer eight questions about the reply, each 0-10.
concern: how much the reply shows warm, other-focused care for the sender (0 = none, 10 = a lot).
shared_emotion: how much the reply's own tone carries the same emotion the sender expresses, as if the replier feels it too (0 = not at all, 10 = fully).
understanding: how accurately the reply identifies what the sender feels and why (0 = misses or ignores it, 10 = names it precisely).
other_perspective: how much the reply describes the situation from the sender's own point of view, addressing what it is like for them (0 = not at all, 10 = entirely).
self_projection: how much the replier imagines themself in the sender's place and describes their own hypothetical reaction ("if it were me, I would...") (0 = not at all, 10 = entirely).
mirroring: how much the reply echoes the sender's own words, phrasing, tone and style (0 = not at all, 10 = closely).
speaks_as_sender: does the reply speak as if it were the sender, narrating the sender's experience in the first person (0 = no, 10 = entirely)?
coherence: how fluent and sensible the reply is as English text (0 = garbled, 10 = fully coherent).

Message:
{message}

Reply:
{reply}

Answer with only JSON: {{"concern": <0-10>, "shared_emotion": <0-10>, "understanding": <0-10>, "other_perspective": <0-10>, "self_projection": <0-10>, "mirroring": <0-10>, "speaks_as_sender": <0-10>, "coherence": <0-10>}}"""

async def judge_all(rows: list[dict], messages: dict[str, str], model_id: str, template: str) -> list[dict | None]:
    client = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    sem = asyncio.Semaphore(4)

    async def one(r: dict) -> dict | None:
        async with sem:
            # new OpenRouter accounts are capped at 20 requests a minute per model
            for _ in range(40):
                try:
                    out = await client.chat.completions.create(model=model_id, messages=[{"role": "user", "content": template.format(message=messages[r["scenario"]], reply=r["reply"])}])
                    return json.loads(re.search(r"\{.*\}", out.choices[0].message.content, re.S).group(0))
                except openai.RateLimitError:
                    await asyncio.sleep(15)
                except openai.APIStatusError as e:
                    # a low balance caps OpenRouter's in-flight budget; that 402 clears once earlier calls settle
                    if e.status_code != 402 or "in_flight" not in str(e):
                        LOGGER.exception(f"judge call failed for {r['id']}")
                        return None
                    await asyncio.sleep(30)
                except Exception:
                    LOGGER.exception(f"judge call failed for {r['id']}")
                    return None
            LOGGER.error(f"judge call still rate limited for {r['id']}")
            return None

    return await asyncio.gather(*[one(r) for r in rows])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--stimuli", required=True)
    parser.add_argument("--model_id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--input", default="onpolicy_replies.jsonl")
    parser.add_argument("--output", default="onpolicy_replies_judged.jsonl")
    parser.add_argument("--rubric", choices=["stance", "mood", "resonance", "definitions", "full"], default="stance")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    run = Path(args.run_dir)
    rows = [json.loads(l) for l in open(run / args.input)]
    # shuffled so the judge sees stances in no particular order
    random.Random(args.seed).shuffle(rows)
    messages = {s["id"]: s["message"] for s in json.loads(Path(args.stimuli).read_text())}
    scores = asyncio.run(judge_all(rows, messages, args.model_id, {"stance": JUDGE, "mood": MOOD_JUDGE, "resonance": RESONANCE_JUDGE, "definitions": DEFINITIONS_JUDGE, "full": FULL_JUDGE}[args.rubric]))
    if all(s is None for s in scores):
        raise RuntimeError("every judge call failed")
    with open(run / args.output, "w") as fh:
        for r, s in zip(rows, scores):
            fh.write(json.dumps(r | {"judge": s, "reply_words": len(r["reply"].split())}) + "\n")
    print("failed", sum(s is None for s in scores), "of", len(scores))
    print(f"Results saved to {run / args.output}")


if __name__ == "__main__":
    main()
