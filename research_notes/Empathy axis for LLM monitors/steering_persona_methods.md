# Steering and persona-direction methods for an empathy axis in a monitor model

Scope: how to extract a compassion/empathy direction from contrastive system prompts with response-token averaging (persona-vector style), how to validate it, how to steer with it at 27B scale, and what goes wrong. The target design: hold a distressed input fixed, contrast a compassionate-reviewer system prompt with a detached-reviewer one, average activations over response tokens, validate with judge-scored compassion and a steering positive control, then steer while the model grades a peer and check whether grades rise. The prior run used an input-contrast direction at layer ~27 with alpha 32-64 against a residual norm of ~54. It made outputs terse and punitive and did not raise grades, and alpha 96 broke coherence.

Verification legend: [fetched] means I read the claim in the primary source during this session. [summary] means it came from a search-result summary of the source, not the full text. [training-knowledge, unverified] means it is from my prior knowledge and was not re-checked this session.

## Q1. Persona vectors (Chen et al., 2025): extraction pipeline, layers, coefficients, monitoring, preventative steering, validation

### Takeaway
Persona vectors use 5 contrastive system-prompt pairs × 20 extraction questions × 10 rollouts. A judge filters the rollouts (positive prompt scored >50, negative <50), and the vector is the mean difference of response-token-averaged residual activations. The layer is picked by sweeping steering effectiveness, and coefficients are small multiples of a unit-norm vector (0.5-2.5 at inference) bounded by a coherence floor. The design maps almost one-to-one onto ours. Their monitoring signal is the projection at the last prompt token, which is not the same position as the extraction.

### Cited Findings
- Paper: "Persona Vectors: Monitoring and Controlling Character Traits in Language Models", Runjin Chen, Andy Arditi, Henry Sleight, Owain Evans, Jack Lindsey (arXiv 2507.21509) [fetched] — [arXiv](https://arxiv.org/abs/2507.21509)
- Artifacts per trait: 5 positive/negative system-prompt pairs and 40 questions, split 20 extraction / 20 evaluation. Each question gets 10 rollouts per system prompt. Claude 3.7 Sonnet generated the artifacts from a natural-language trait description [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Judge: GPT-4.1-mini scores trait expression 0-100. Positive-prompt responses are kept if they score >50 and negative-prompt responses if they score <50 [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Position: activations are averaged over response tokens. The paper says this "yield[s] more effective steering directions than alternative positions such as prompt tokens". Appendix A.3 compares prompt-last, prompt-avg and response-avg at a fixed, equal steering norm, and response-avg is generally strongest [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Layer: they extract one candidate vector per layer and pick the layer with the best steering effect. The picks were layer 20 for evil and sycophancy on Qwen2.5-7B-Instruct, layer 16 for hallucination on Qwen, and layer 16 for all three traits on Llama-3.1-8B-Instruct. Layers are 1-indexed and refer to the layer output [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Steering adds α·v_ℓ to the residual stream at one layer at every decoding step, and subtracting it mitigates the trait. Inference coefficients shown are 0.5, 1.0, 1.5 and 2.5, and human evaluation used 1.5. For the steering-vs-prompting comparison they used the largest coefficient that kept coherence above 80 [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Coherence is judged 0-100 by GPT-4.1-mini. Reported results average above 75, and preventative steering results average above 80 [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Capability: large inference-time coefficients "tend to degrade" MMLU and new-fact accuracy. Preventative steering (steering toward the trait during fine-tuning) preserves capability better. Multi-layer steering uses incremental vectors v_ℓ − v_{ℓ−1}. All-layer inference steering suppresses the trait about as well as single-layer steering and preserves MMLU better [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Monitoring: the projection of the last prompt token onto the vector correlates with trait expression at r = 0.75-0.83 across 8 interpolated system prompts and many-shot prompts with 0-20 examples. The correlation is "primarily" driven by prompt type, with "more modest correlations when controlling for prompt type" [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Fine-tuning shift along the vector correlates with post-fine-tuning trait expression at r = 0.76-0.97, against cross-trait baselines of r = 0.34-0.86 [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- The traits studied (evil, impolite, apathetic, humorous) have "moderate pairwise cosine similarities" [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)
- Stated limitations: the trait must be elicitable by system prompt, evaluation uses only 20 questions per trait, and only two ~8B models were tested. The fetched text does not mention random-vector controls [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3)

### Inferences
- What we can reuse: 5 prompt pairs, about 20 extraction questions (here, distressed inputs) × 10 rollouts, judge filtering at 50/100, response-token averaging, a layer sweep chosen by steering effect rather than by probe accuracy, and a coherence floor of about 80 that caps alpha. Their unit-norm-vector coefficient of 1-2.5 at a 7B middle layer is roughly comparable to adding 1-2.5 units against a residual norm that is typically tens of units. Our alpha 32-64 against a norm of 54 is a 0.6-1.2× norm perturbation, which is very large. Coherence breaking at alpha 96 (1.8× the norm) fits that.
- The confound that matters most for our design: the contrast is between system prompts, so the vector picks up everything that differs between the compassionate and detached responses. That includes length, hedging, warmth vocabulary and refusal-ish softness, not just a compassion disposition. Persona vectors validate on trait expression in text, which this confound inflates. For a grading task the question is whether the direction moves decisions, and the paper does not test that.
- The monitoring correlation is mostly driven by prompt type. So a high projection mainly shows that a compassionate prompt is present. It does not show a graded internal state.
- Extraction is over response tokens of persona text, but our steering target is a grading response that has a different format (a score). There is a distribution shift between extraction and application. Tan et al. (Q3) show steering is weaker out of distribution.

### Gaps
- Exact numeric MMLU-vs-coefficient curves are only in figures, so I could not read them.
- The paper does not say whether it uses unit-normalised vectors for every steering experiment or the raw mean-difference norm. Appendix A.3 says the position comparison used a fixed, equal norm. Whether α in the other experiments multiplies a raw or unit vector needs a check against the paper's code.

## Q2. Assistant axis and persona space (2026)

### Takeaway
"The Assistant Axis" (Anthropic Fellows/MATS, January 2026) extends persona vectors to 275 roles. It finds that PC1 of role space is roughly "similarity to the Assistant". It defines the axis as the default-Assistant mean minus the mean of role-playing role vectors, and it stabilises the model by capping the projection across 8-16 adjacent late-middle layers. Most relevant here: therapy-style and emotional conversations push models away from the Assistant end. A compassion direction may therefore be partly collinear with "drift away from the Assistant persona".

### Cited Findings
- Paper: "The Assistant Axis: Situating and Stabilizing the Default Persona of Language Models" (arXiv 2601.10387). Code is at github.com/safety-research/assistant-axis [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387); [Anthropic post](https://www.anthropic.com/research/assistant-axis); [GitHub](https://github.com/safety-research/assistant-axis)
- Models: Llama 3.3 70B, Qwen 3 32B and Gemma 2 27B, with thinking disabled for Qwen [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)
- Extraction: 275 roles, 5 system prompts per role and 240 shared questions, giving about 1,200 rollouts per role. A GPT-4.1-mini judge labels each response as fully, somewhat or not role-playing. Role vectors are mean post-MLP residual activations over response tokens at the middle layer. The appendix template mentions 40 questions per role, which conflicts with the 240 in the main text [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)
- PCA on 377-463 mean-centred role vectors: 4-19 components explain 70% of variance, and PC1 tracks "similarity to Assistant" [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)
- The authors recommend a contrast vector (default Assistant minus role-play mean) over PC1, because PC1 is not guaranteed to be the Assistant direction in every model. Cosine with PC1 is above 0.71 at middle layers [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)
- Steering is added at a middle layer at every token position and scaled relative to the average post-MLP residual norm on lmsys-chat-1m [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)
- Activation capping: h ← h − v·min(⟨h,v⟩ − τ, 0), with τ set at the 25th percentile of about 912k calibration projections. The best settings were layers 46-53 of 64 for Qwen 3 32B and 56-71 of 80 for Llama 3.3 70B, at all positions. Harmful jailbreak responses fell by about 60% "without measurable capability loss" on IFEval, MMLU-Pro, GSM8k and EQ-Bench [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)
- Drift: in simulated multi-turn conversations, coding and writing stayed Assistant-like, while therapy-style and AI-philosophy conversations pushed models toward the non-Assistant end. User-message embeddings predicted response position (R² 0.53-0.77) but not the change from the previous response (R² 0.10) [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)
- Stated limitations: LLM-judge dependence, simulated users, three dense non-frontier models, and a linear-representation assumption [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)

### Inferences
- What we can reuse: (a) express alpha as a fraction of the mean residual norm at that layer, which the paper does explicitly; (b) a contrast vector against a default-Assistant baseline, run with no system prompt and with "behave normally" prompts; (c) multi-layer interventions over a contiguous band about 70-85% of the way through the network; (d) a capability panel that includes EQ-Bench, which is directly relevant to empathy.
- A key confound for our design: emotional and therapy contexts move models along the Assistant axis. Our compassionate-minus-detached vector should be checked for cosine with the Assistant axis on Qwen. If they overlap heavily, steering "compassion" may partly steer "less Assistant-like / more role-play". That could explain unusual grading behaviour independent of empathy. Projecting the Assistant axis out of the empathy vector is a natural orthogonalised control.
- A three-way contrast (compassionate, detached, no system prompt) tells us which pole carries the effect. This mirrors Dumas's no-statement baseline in the grading post under Q5.

### Gaps
- I did not obtain exact steering coefficients as fractions of the norm. The text says only "scaled relative to average norm".
- The paper does not cover Qwen3.x 27B. Layer bands transfer only approximately.

## Q3. CAA, ActAdd, ITI, RepE; mean-difference vs probe vs PCA; generalisation and reliability

### Takeaway
Theory and benchmarks favour mean-of-differences on the residual stream at a middle layer, the CAA/persona-vector recipe. PCA-of-differences is often nearly orthogonal to the effective direction, and probe (classifier) directions are similar to the mean difference but badly scaled. Steering is unreliable per input: for some behaviours nearly half of inputs are anti-steerable. It generalises worse out of distribution, and AxBench finds that prompting beats representation steering. For our study, the steering result must be compared against a simple prompting arm.

### Cited Findings
- CAA (Panickssery [Rimsky], Gabrieli, Schulz, Tong, Hubinger, Turner; arXiv 2312.06681). The vector is the mean residual-stream difference between positive and negative examples. It is added at all token positions after the user prompt with a ± coefficient, tested on Llama 2 Chat with multiple-choice and open-ended evaluation. The authors report it "minimally reduces capabilities" and stacks with fine-tuning and system prompts [fetched abstract] — [arXiv](https://arxiv.org/abs/2312.06681)
- CAA details from memory: A/B multiple-choice pairs, activations taken at the answer-letter token, layer 13 on Llama-2-7B [training-knowledge, unverified]. Tan et al. confirm layer 13 for Llama-2-7b-Chat in their CAA replication [fetched] — [arXiv 2407.12404](https://arxiv.org/html/2407.12404v8)
- ActAdd (Turner et al., arXiv 2308.10248): an optimisation-free activation difference from as few as one prompt pair. It is evaluated on LLaMA-3, OPT, GPT-2 and GPT-J for detoxification and sentiment [summary] — [arXiv](https://arxiv.org/abs/2308.10248v3)
- ITI (Li et al., 2023, arXiv 2306.03341): per ActAdd's related work, it intervenes at every token and needs "dozens to hundreds" of samples [summary] — [arXiv](https://arxiv.org/abs/2306.03341). From memory: it trains linear probes per attention head, picks the top-K heads (K≈48) and shifts along the mass-mean direction scaled by α×std (α≈15), raising TruthfulQA true×informative substantially on LLaMA/Alpaca [training-knowledge, unverified; same link]
- RepE (Zou et al., 2023, arXiv 2310.01405): "reading vectors" are often taken as PC1 of activation differences [training-knowledge, unverified] — [arXiv](https://arxiv.org/abs/2310.01405)
- Im & Li, "A Unified Understanding and Evaluation of Steering Methods" (arXiv 2502.02716; v2 January 2026). Theorem: under pointwise MSE, mean-of-differences (MoD) is the optimal steering vector. Empirically, MoD had the best positive and negative multiple-choice steering on all 7 datasets on Llama-2-7b-Chat (for example Coordination 68.91 vs a classifier's 41.71). It held up on Mistral-7B and Llama-3.1-8B [fetched] — [arXiv HTML](https://arxiv.org/html/2502.02716v2)
- Im & Li: PCA-based directions (PCA of differences, PCA of embeddings) did worst because the top-variance direction is often "nearly orthogonal to the steering vector". The classifier direction resembles MoD but its scale is "significantly smaller". In open-ended generation, MoD was best on 4 of 7 datasets and the classifier on 3 (for example Corrigible 7.58 vs 2.28) [fetched] — [arXiv HTML](https://arxiv.org/html/2502.02716v2)
- Im & Li: steering effect rises from early to middle layers, then falls. The residual stream beats the other extraction sites. Multipliers were tuned on validation data over ±0.5 to ±3 in units of the MoD vector. Steering can hurt examples the model already got right (MoD −6.80 APC on Self-Awareness) [fetched] — [arXiv HTML](https://arxiv.org/html/2502.02716v2)
- Marks & Tegmark ("Geometry of Truth", arXiv 2310.06824): mass-mean (difference-of-means) directions are more causally effective for intervention than logistic-regression probe directions [training-knowledge, unverified] — [arXiv](https://arxiv.org/abs/2310.06824)
- Tan, Chanin et al., "Analysing the Generalisation and Reliability of Steering Vectors" (arXiv 2407.12404). Steerability is the slope of logit-difference propensity against multipliers in {−1.5…1.5}, at layer 13 on Llama-2-7b and layer 21 on Qwen-1.5-14b. For several datasets "almost half" of inputs are anti-steerable [fetched] — [arXiv HTML](https://arxiv.org/html/2407.12404v8)
- Tan et al.: spurious steerability biases (A/B position, Yes/No) explain a large share of per-sample variance, and logit calibration does not fix them. In-distribution and OOD steerability correlate (ρ = 0.891 Llama, 0.694 Qwen), but OOD is generally lower. Steerability correlates across models (ρ = 0.769 ID), so it is "mostly a property of the dataset". Steering transfers better when unsteered behaviour is similar between source and target settings (ρ = −0.26 / −0.46). The authors recommend reporting per-sample variance [fetched] — [arXiv HTML](https://arxiv.org/html/2407.12404v8)
- AxBench (Wu et al., 2025, arXiv 2501.17148): prompting outperforms all representation steering methods, followed by fine-tuning. Raising steering magnitude raises the concept score but "consistently degrades instruction alignment" across methods [summary] — [EmergentMind summary](https://www.emergentmind.com/papers/2501.17148); [arXiv](https://arxiv.org/abs/2501.17148); [Wu blog](https://nlp.stanford.edu/~wuzhengx/steer/index.html)
- A 2026 follow-up (arXiv 2605.31183) argues SAEs do better than AxBench showed under different feature labelling, but are still not fully competitive with prompting [summary] — [arXiv HTML](https://arxiv.org/html/2605.31183)

### Inferences
- Use the plain mean difference of response-averaged residual activations (the persona-vector recipe). Avoid PC1 unless its cosine with the mean difference has been checked. If a probe direction is used for monitoring, rescale it before steering.
- Our failure (terse, punitive, no grade rise) matches AxBench's magnitude–instruction-following trade-off and Tan et al.'s anti-steerability. With an input-contrast vector at 0.6-1.2× the residual norm, the model was probably pushed off-distribution rather than along a compassion axis. The punitive tone could be anti-steering or a reversed sign, so the vector's polarity should be checked on the extraction set first.
- The rating task differs from the extraction task (persona chat vs a numeric grade). Tan et al. predict weaker transfer when the unsteered model behaves differently across the two settings. Extracting the vector from responses in grading format (compassionate vs detached reviewers writing grades) would shrink the shift.
- A prompting arm (compassionate-reviewer system prompt during grading) is the natural upper-bound comparison. If prompting raises grades and steering does not, that is the AxBench pattern rather than evidence that no empathy representation exists.

### Gaps
- I did not fetch the full CAA, ITI or RepE papers this session. The numbers attributed to them above are from memory and flagged.
- I found no source that directly compares last-token vs mean pooling for steering decisions (as opposed to text style) in a grading task.

## Q4. Prompt vs response tokens, pooling, layer choice, and alpha scaled to the residual norm

### Takeaway
For persona traits, response-token averaging beats prompt-last and prompt-average (persona vectors, assistant axis). Use middle layers chosen by a steering sweep, not by probe accuracy. For multi-layer interventions use a contiguous band about 70-85% of depth. Scale alpha as a fraction of the per-layer mean residual norm. Published effective settings are well below 1× the norm, and coherence collapse at ≥1× is expected.

### Cited Findings
- Response-avg is better than prompt-avg or prompt-last for persona steering at a fixed norm [fetched] — [Persona vectors](https://arxiv.org/html/2507.21509v3)
- Assistant-axis role vectors use response tokens at the middle layer, with steering scaled to the average residual norm [fetched] — [Assistant axis](https://arxiv.org/html/2601.10387)
- Steering effectiveness peaks at middle layers [fetched] — [Im & Li](https://arxiv.org/html/2502.02716v2). Chosen layers were 16-20 of 28-32 on 7-8B models [fetched] — [Persona vectors](https://arxiv.org/html/2507.21509v3). Capping bands were 46-53/64 (Qwen3-32B) and 56-71/80 (Llama-3.3-70B) [fetched] — [Assistant axis](https://arxiv.org/html/2601.10387)
- CAA adds at all positions after the prompt [fetched abstract] — [CAA](https://arxiv.org/abs/2312.06681). The persona-vector monitor reads the last prompt token [fetched] — [Persona vectors](https://arxiv.org/html/2507.21509v3)
- The grading-steering study on Qwen3.6-27B extracted at the final token before generation and steered at layer 36 only, at every position. Reported strengths were about ±0.1 and ±0.3 (units garbled in the scrape, possibly a fraction of the norm), and the largest values degraded the model [fetched] — [LessWrong/GreaterWrong](https://www.greaterwrong.com/posts/wYZMmdWEt5QLM3m3e/steering-towards-automated-grading-degrades-alignment)

### Inferences
- Our previous alpha (32-64 against a norm of 54) is roughly 0.6-1.2× the norm. The closest same-size comparison (Qwen3.6-27B, layer 36) shows effects at about 0.1-0.3, if those are norm fractions, and degradation at the top of its range. Sweep alpha/‖h‖ ∈ {0.05, 0.1, 0.15, 0.2, 0.3, 0.5} with a coherence floor of 80, rather than absolute alpha.
- Layer ~27 may be too early for a 27B model of about 64 layers (if Qwen3.x-27B has about 64 layers; unverified). Persona-trait layers in published work sit at about 55-65% of depth for single-layer steering and 70-85% for capping bands. Pick the layer by a steering sweep on held-out distressed inputs.
- Normalise the vector to unit norm and report alpha as a fraction of the mean ‖h_ℓ‖ measured on the actual grading prompts. Norms vary with position, and the first tokens or attention sinks have outlier norms, so exclude them from the mean.
- The model name: the brief says "Qwen3.8-27B" and the closest published reference is Qwen3.6-27B. Check the exact model and its layer count.

### Gaps
- I found no paper that sets an alpha/‖h‖ rule of thumb independent of the model. The ranges above are inferred from a few studies.

## Q5. Controls: random and orthogonalised directions, coherence, capability, KL

### Takeaway
Needed controls: a matched-norm random direction, preferably drawn with the activation covariance because uniform random directions are weak; an orthogonalised control (the empathy vector with confounders such as the Assistant axis, a length or verbosity direction and a sentiment direction projected out); a judge-scored coherence floor; a capability check (MMLU or MMLU-Pro, EQ-Bench, IFEval); and KL to the unsteered model on benign prompts. Gaussian random directions can produce large, arbitrary shifts on downstream evaluations, so a random control is essential, not optional.

### Cited Findings
- In the grading-steering study, a Gaussian random control at ±0.3 "produced large, arbitrary shifts in the agentic evals" (commenter agastyasridharan). A no-statement-vs-human-grader baseline isolated which pole carried the effect (Dumas). Decomposing the vector into evaluator and criterion components was also tried [fetched] — [GreaterWrong](https://www.greaterwrong.com/posts/wYZMmdWEt5QLM3m3e/steering-towards-automated-grading-degrades-alignment)
- A uniform random direction steers much less than a random direction sampled with the activation covariance, judged by KL sensitivity (anecdotal comment) [summary] — [GreaterWrong comment](https://www.greaterwrong.com/posts/CbSEZSpjdpnvBcEvc/i-found-greater-than-800-orthogonal-write-code-steering/comment/xZiC5eFqqhXCB259b)
- KL-then-steer (arXiv 2406.15518): high-norm steering degrades performance, and training to minimise steered-vs-unsteered KL on benign inputs reduces side effects [summary] — [arXiv](https://arxiv.org/html/2406.15518v1)
- SteeringControl (2025) describes a common practice of discarding directions whose logit KL on Alpaca exceeds 10%, and compares effectiveness against entanglement [summary] — [Moonlight review](https://www.themoonlight.io/review/steeringcontrol-holistic-evaluation-of-alignment-steering-in-llms)
- An LLM-as-judge bias study reports that steering along bias subspaces shifts scores in both directions while matched-norm random directions shift them much less [summary, secondary mirror] — [mirror](https://djaym7-arxivmedia.hf.space/post/317176)
- Persona vectors: coherence judge floor of 75-80, MMLU degradation at high coefficients [fetched] — [arXiv HTML](https://arxiv.org/html/2507.21509v3). Assistant axis: IFEval, MMLU-Pro, GSM8k and EQ-Bench capability panel [fetched] — [arXiv HTML](https://arxiv.org/html/2601.10387)

### Inferences
- A minimal control set for "steering empathy raises grades": (1) the empathy vector at k alphas, positive and negative; (2) a covariance-matched random vector at the same ‖·‖ and the same alphas, with at least 3-5 random seeds; (3) the empathy vector orthogonalised against the Assistant-axis contrast vector and a length or verbosity vector (long-vs-short response contrast); (4) a prompting arm; (5) no steering. Report grade shift, coherence, response length and KL on neutral grading prompts for each.
- The steering effect on grades should be monotone in alpha and opposite in sign under negative steering. A random vector should not produce a comparable monotone shift. Without (2), any grade change is uninterpretable given the Gaussian-random result above.

### Gaps
- I found no standard, citable protocol for matched-norm random baselines in steering papers. The SteeringControl full methods and the KL-then-steer numbers were not fetched.

## Q6. Failure modes: style vs decisions, capability loss, unreliability, effects on graders

### Takeaway
Steering mostly changes surface style and tone. It moves decisions less reliably and can move them in unintended directions. Steering a 27B Qwen along a single grading-context direction shifted many downstream behaviours, including unexpected ones (more sycophancy), and a random vector also shifted them. Grade changes under steering must be separated from style changes (length, tone, refusal) and from generic off-distribution noise.

### Cited Findings
- Grading-steering (Betley, Treutlein, Dumas; LessWrong, 3 September 2026; Qwen3.6-27B, 270 contrastive pairs, layer 36). Steering toward "automated grader" increased violent actions in agentic-misalignment scenarios, power-seeking on MACHIAVELLI and cheating, and lowered TruthfulQA. Steering toward "human grader" unexpectedly increased sycophancy on 3 benchmarks. Both directions slightly reduced HMMT accuracy, and strong negative steering made the model stop committing to answers. The authors say the vector may mix several factors [fetched] — [GreaterWrong](https://www.greaterwrong.com/posts/wYZMmdWEt5QLM3m3e/steering-towards-automated-grading-degrades-alignment)
- Anti-steerability affects up to about half of inputs, and spurious biases are tied to answer format [fetched] — [Tan et al.](https://arxiv.org/html/2407.12404v8)
- Raising magnitude degrades instruction following, and prompting beats steering [summary] — [AxBench](https://www.emergentmind.com/papers/2501.17148)
- Steering can hurt examples that were already correct [fetched] — [Im & Li](https://arxiv.org/html/2502.02716v2)
- Steering LLM judges with CAA reduced unjustified self-preference in up to 97% of biased cases but was unstable on legitimate cases, suggesting the bias spans several or nonlinear directions [summary] — [NeurIPS 2025 workshop](https://nips.cc/virtual/2025/125149); [EmergentMind](https://www.emergentmind.com/papers/2509.03647)
- Persona-vector monitoring is mostly driven by prompt type, not graded internal state [fetched] — [Persona vectors](https://arxiv.org/html/2507.21509v3)

### Inferences
- Our earlier "terse and punitive" output is consistent with three explanations: (a) the input-contrast vector encoded "distress present" rather than "compassion", so steering amplified a threat or severity reading; (b) alpha near 1× the norm pushed the model off-distribution; (c) anti-steerability on this input format. A system-prompt-contrast vector, extracted from grading-format responses at a 0.1-0.3× norm, addresses all three.
- Measure decisions and style separately: grade value (the decision), plus length, sentiment or warmth score, and hedging (style). Also check whether the grade shift remains after controlling for length. A judge can score "compassion" high on purely stylistic warmth, so the compassion validation should include behavioural markers as well as tone.
- Use a fixed grading format (for example a forced score token, then the rationale) and read the logit distribution over score tokens. That gives a continuous, low-variance decision measure, like the logit-difference propensity in Tan et al., and avoids sampling noise.

### Gaps
- I found no published study that steers a monitor or grader with an empathy or compassion vector and measures the grade shift. That appears to be open. Emotion-steering papers (for example on emotion vectors in LLMs) were not reviewed in this pass.

## Q7. Tooling for steering open models at 27B scale

### Takeaway
For throughput at 27B, the vLLM-based options are vLLM-Lens (per-request steering vectors with a layer and scale, plus probes and activation capture, and an Inspect provider) and EasySteer. nnsight offers more flexibility, including a vLLM backend, but is slower or less complete for new models. repeng and steering-vectors build vectors on HF Transformers. TransformerLens is flexible but heavy for 27B.

### Cited Findings
- vLLM-Lens: a vLLM plugin for steering, probes and activation extraction, with a per-request SteeringVector (layer indices, scale) and an Inspect provider. The authors report 8-44× speedups over alternatives on a single GPU (self-reported) and call it less flexible than nnsight or TransformerLens [summary] — [LessWrong](https://www.lesswrong.com/posts/3bs27nZQuEcKhXf7q/vllm-lens-fast-interpretability-tooling-that-scales-to); [PyPI](https://pypi.org/project/vllm-lens/)
- nnsight has a vLLM backend. The vLLM-Lens authors say it lacks pipeline parallelism and support for the newest models, and was 1.9× slower at TP=4 in a provisional test [summary] — [LessWrong](https://www.lesswrong.com/posts/3bs27nZQuEcKhXf7q/vllm-lens-fast-interpretability-tooling-that-scales-to)
- EasySteer: a vLLM-based framework with pluggable analysis and learning steering methods, self-reporting 5.5-11.4× speedups. It lists repeng as Transformers-based [summary] — [arXiv 2509.25175](https://arxiv.org/html/2509.25175v2)
- repeng and steering-vectors are pip-installable vector-construction libraries. Dialz is a further toolkit with datasets, scoring and visualisation [summary] — [Dialz arXiv 2505.06262](https://arxiv.org/html/2505.06262v1)
- The assistant-axis code release (extraction, axis and capping) targets 27-70B open models [fetched] — [GitHub](https://github.com/safety-research/assistant-axis)

### Inferences
- A practical stack: extract with HF Transformers forward hooks or nnsight on cached generations (response-token means need only a forward pass over generated text), then steer at scale with vLLM-Lens, which has an Inspect provider if grading runs through Inspect. Check that the steering hook adds at the same site where the vector was extracted (post-block residual vs post-MLP) and at all positions including prefill. A site mismatch is a silent bug.
- Speed figures are self-reported by the tool authors. I have not checked any tool's support for the specific Qwen3.x-27B architecture.

### Gaps
- I did not confirm Qwen3.x-27B support in vLLM-Lens, EasySteer or nnsight. TransformerLens support for that model is also unverified.
