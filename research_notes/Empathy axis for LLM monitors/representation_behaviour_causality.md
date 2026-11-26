# Representation-behaviour dissociation and causal-mediation methods for testing perceive distress -> empathic stance -> lenient grade

Link status: links marked (checked) came back in a web search during this session (2026-11-20). Links marked (from memory) are arXiv IDs I know but did not re-fetch this session. They are very likely right, but check them before citing.

## 1. "Knows but doesn't act": when decodable representations do or do not drive behaviour

### Takeaway
A direction you can decode perfectly is often not one the model uses. There are two standard ways this happens. Either the information is present but the behaviour is read from a different variable, or the "same" concept has two separate representations: one for perceiving it, one for acting on it. Zhao et al. 2025 is the closest analogue to this project. They find that harmfulness, the perception, and refusal, the action, are separate directions at different token positions, and that the two can disagree.

### Cited findings
- **Harmfulness vs refusal (Zhao, Huang, Wu, Bau, Shi 2025).** LLMs mainly encode harmfulness at the instruction's final token and refusal at the post-instruction tokens. Clustering at the instruction token groups prompts by harmfulness; clustering at the post-instruction position groups them by the model's actual refusal. Steering a harmless prompt along the harmfulness direction makes the model treat it as harmful. Steering along the refusal direction produces refusals without changing the harmfulness judgment. Some jailbreaks suppress refusal while leaving the internal harmfulness signal intact. The paper's "Latent Guard" uses the harmfulness representation as a classifier and matches or beats Llama Guard 3 8B. — [arXiv 2507.11878](https://arxiv.org/abs/2507.11878) (checked)
- **Refusal direction (Arditi et al. 2024).** A case where a single direction is causal. Ablating one difference-in-means direction from the residual stream at every layer and position disables refusal across 13 open chat models up to 72B, and adding it induces refusal. — [arXiv 2406.11717](https://arxiv.org/abs/2406.11717) (from memory)
- **Truth representations vs outputs.**
  - CCS (Burns et al. 2022) recovers truth-like directions without labels and reports that they stay accurate when the model is prompted to output falsehoods, so latent knowledge and output can diverge. — [arXiv 2212.03827](https://arxiv.org/abs/2212.03827) (from memory)
  - Marks & Tegmark ("Geometry of Truth") find linear truth directions. Unlike many probe papers, they test them causally: patching or adding the direction flips the model's true/false outputs, and mass-mean probes were the most causally implicated. — [arXiv 2310.06824](https://arxiv.org/abs/2310.06824) (from memory)
  - Azaria & Mitchell train a classifier on hidden states that detects when the model is producing a false statement (SAPLMA). — [arXiv 2304.13734](https://arxiv.org/abs/2304.13734) (from memory)
- **Orgad et al. 2024, "LLMs Know More Than They Show".** Truthfulness information is concentrated at the exact-answer tokens. Error-detection probes often fail to generalise across tasks. A model can encode the correct answer internally yet consistently generate a wrong one, and choosing among sampled answers with the probe improves accuracy. — [arXiv 2410.02707](https://arxiv.org/abs/2410.02707) (from memory)
- **Probes decodable but not used.**
  - Ravichander, Belinkov & Hovy ("Probing the Probing Paradigm") show probes can decode properties the model does not need for its task. Probe accuracy does not imply use. — [arXiv 2005.00719](https://arxiv.org/abs/2005.00719) (from memory)
  - Hewitt & Liang propose control tasks (selectivity), because an expressive probe can learn the task itself. — [arXiv 1909.03368](https://arxiv.org/abs/1909.03368) (from memory)
  - Belinkov's review of probing classifiers covers the correlational-vs-causal gap. — [arXiv 2102.12452](https://arxiv.org/abs/2102.12452) (from memory)
- **Amnesic probing (Elazar et al. 2021).** Remove a property with INLP and measure how much behaviour changes. Some highly decodable properties barely matter to the LM objective when removed, and decodability did not predict importance. — [arXiv 2006.00995](https://arxiv.org/abs/2006.00995) (from memory); INLP: [arXiv 2004.07667](https://arxiv.org/abs/2004.07667) (from memory); LEACE, closed-form linear erasure: [arXiv 2306.03819](https://arxiv.org/abs/2306.03819) (from memory)
- **Evaluation awareness.**
  - Abdelnabi & Salem probe and steer "test awareness" in reasoning models, using the probe weights to steer. Steering toward awareness changed harmful-task compliance. Steering toward unawareness also increased harmful-task execution for Qwen3, so the effect is not monotonic or simple. — [arXiv 2505.14617](https://arxiv.org/abs/2505.14617) (checked; numbers seen only in summaries); code: [github.com/microsoft/Test_Awareness_Steering](https://github.com/microsoft/Test_Awareness_Steering)
  - Nguyen et al., "Probing evaluation awareness of language models". — [arXiv 2507.01786](https://arxiv.org/abs/2507.01786) (from memory; I did not confirm details)
- **Anthropic, emotion concepts in Claude Sonnet 4.5 (Apr 2026).**
  - Method: 171 emotion-concept vectors built from model-written stories.
  - Causal effects: steering "desperate" raised blackmail (22% baseline on an early snapshot) and reward hacking; steering "calm" lowered both. "Anger" was non-monotonic: moderate steering raised blackmail, but high steering made the model expose the affair company-wide, which threw away its leverage.
  - Desperation steering raised cheating with no visible emotional markers in the text.
  - The vectors are described as mostly local: they track the emotion relevant to the current or upcoming output (for example a story character's), not a persistent state of the model.
  - Sources: [anthropic.com/research/emotion-concepts-function](https://www.anthropic.com/research/emotion-concepts-function) (checked); full paper: [transformer-circuits.pub/2026/emotions](https://transformer-circuits.pub/2026/emotions/index.html) (link taken from the post; I did not fetch it).
- **Doubts about truth probes.** Levinstein & Herrmann, "Still no lie detector for language models". — [arXiv 2307.00175](https://arxiv.org/abs/2307.00175) (from memory). Farquhar et al. show CCS-style methods can latch onto other salient features. — [arXiv 2312.10029](https://arxiv.org/abs/2312.10029) (from memory)

### Inferences
- An AUC of 1.0 for "the peer is distressed" is expected rather than informative. Distress in the input is lexically obvious, so almost any layer will separate it. That makes it a perception or input-feature direction. Following Zhao et al., it is plausibly not the variable the grade is computed from.
- If the emotion vectors in Qwen behave like Anthropic's (local, tracking whoever's emotion is relevant), the distress direction may encode *the peer's* state. Leniency would need a different variable: the *grader's own* stance toward the peer.
- So "steering the distress direction doesn't raise grades" fits the hypothesis that the chain breaks right after perception. It also fits a more boring explanation: the steering was applied at the wrong position or layer. Zhao's result is that the action variable sits at a different token position from the perception variable.
- Run a selectivity control. Decode a grade-irrelevant surface feature of the same salience (for example topic or the peer's name) with the same probe. If it also reaches AUC ~1, the distress AUC means nothing about use.

### Gaps
- I found no paper that tests an emotion-perception -> stance -> evaluation chain inside an LLM judge or grader. This looks like an open gap.
- I did not verify the Anthropic emotions paper's details beyond the blog post, including whether a "perceived emotion of others" vs "own emotion" split was tested.

## 2. Causal methods: patching, mediation, interchange interventions, ablation, conditional steering

### Takeaway
The toolbox, from cheapest to most rigorous:
1. Steering and additive interventions. These test sufficiency.
2. Directional ablation or erasure. These test necessity.
3. Activation patching between paired clean and corrupt inputs. This tests whether a site carries the difference.
4. Causal mediation analysis. This splits the total effect into direct and indirect parts.
5. Interchange interventions with DAS. These test whether a learned subspace *is* a hypothesised causal variable.

Every method has known illusions, so it needs matched-norm random-direction controls and off-distribution checks.

### Cited findings
- **Causal mediation analysis (Vig et al. 2020).** Defines the total effect, the natural direct effect and the natural indirect effect of a neuron or attention head in carrying gender bias, by intervening on the input and setting the mediator to its value under the other input. This decomposition is directly reusable for distress -> empathy -> grade. — [arXiv 2004.12265](https://arxiv.org/abs/2004.12265) (from memory)
- **ROME causal tracing (Meng et al. 2022).** Corrupt subject embeddings with noise, then restore individual hidden states to locate where factual recall is mediated (mid-layer MLPs at the last subject token). — [arXiv 2202.05262](https://arxiv.org/abs/2202.05262) (from memory)
- **Path patching (IOI circuit, Wang et al. 2022).** Patches the effect of one component on another along a specific path, not the component's total effect. — [arXiv 2211.00593](https://arxiv.org/abs/2211.00593) (from memory)
- **Attribution patching.** A first-order gradient approximation to activation patching that needs two forward passes and one backward pass for all sites at once. AtP* (Kramár et al. 2024) fixes known false negatives, for example attention saturation. — [arXiv 2403.00745](https://arxiv.org/abs/2403.00745) (from memory)
- **Patching best practice.**
  - Zhang & Nanda: the choice of corruption method (Gaussian noise vs symmetric token replacement) and metric (logit difference vs probability) changes conclusions. They recommend symmetric token replacement and logit difference. — [arXiv 2309.16042](https://arxiv.org/abs/2309.16042) (from memory)
  - Heimersheim & Nanda, "How to use and interpret activation patching": denoising tests sufficiency, noising tests necessity, and the two can disagree. — [arXiv 2404.15255](https://arxiv.org/abs/2404.15255) (from memory)
- **Subspace patching illusion (Makelov, Lange, Nanda, ICLR 2024).** Patching along a 1-D subspace can have the intended end-to-end effect by activating a dormant parallel pathway that is causally disconnected from the output in normal operation. Shown in a toy example, in IOI and in factual recall, and used to explain why fact-editing success doesn't track localisation. The authors do not call subspace patching useless. — [arXiv 2311.17030](https://arxiv.org/abs/2311.17030) (checked)
- **Causal abstraction and DAS.**
  - Geiger et al. formalise interchange interventions: run the model on a base input, swap in the activations of a hypothesised variable from a source input, and check whether the output changes the way the high-level causal model predicts. — [arXiv 2301.04709](https://arxiv.org/abs/2301.04709) (from memory)
  - Distributed Alignment Search learns a rotation or subspace with gradient descent so that interchange interventions on it match the high-level model. — [arXiv 2303.02536](https://arxiv.org/abs/2303.02536) (from memory)
  - Tooling: pyvene — [arXiv 2403.07809](https://arxiv.org/abs/2403.07809) (from memory)
  - Mueller et al., "The quest for the right mediator", reviews choosing mediators (neurons, subspaces, SAE features) for causal interpretability. — [arXiv 2408.01416](https://arxiv.org/abs/2408.01416) (from memory)
- **Directional ablation.** Arditi et al. project the direction out of every residual write (above). Tigges et al. find a linear sentiment direction in several models, show by ablation that it carries a large share of sentiment-classification performance, and identify a "summarisation motif" where sentiment is gathered at punctuation and name tokens. — [arXiv 2310.15154](https://arxiv.org/abs/2310.15154) (from memory)
- **Additive steering.** ActAdd — [arXiv 2308.10248](https://arxiv.org/abs/2308.10248); Contrastive Activation Addition (Rimsky et al.) — [arXiv 2312.06681](https://arxiv.org/abs/2312.06681) (both from memory).
- **Conditional activation steering (CAST, Lee et al., IBM).** A condition vector decides whether to apply a behaviour vector, which separates "detect the context" from "act". This maps directly onto perceive -> act. — [arXiv 2409.05907](https://arxiv.org/abs/2409.05907) (from memory)
- **Steering reliability (Tan et al., NeurIPS 2024).**
  - In distribution, steerability varies widely across inputs, and spurious biases drive it.
  - For some inputs the vector produces the opposite of the intended behaviour.
  - Steerability depends more on the dataset than on the model.
  - Out of distribution, vectors often generalise but are brittle to reasonable prompt changes.
  - Source: [arXiv 2407.12404](https://arxiv.org/abs/2407.12404) (checked)
- **Persona vectors (Chen, Arditi, Sleight, Evans, Lindsey 2025).** Automated extraction of trait directions (evil, sycophancy, hallucination) from a natural-language trait description using contrastive system prompts. Finetuning-induced personality shifts correlate strongly with shifts along those directions. This is a ready recipe for an "empathic stance" direction. — [arXiv 2507.21509](https://arxiv.org/abs/2507.21509) (checked); code reportedly under safety-research on GitHub (unverified).

### Inferences
- "Measure whether steering direction A changes the projection on direction B, and then behaviour" is the interventional form of the a-path and b-path of Vig-style mediation.
  - Intervene on A (distress), read B (empathy projection at the grade position): this is the a-path.
  - Intervene on B with A held fixed, read the grade: this is the b-path.
  - Set B to its distressed-run value inside a neutral run (interchange), read the grade: this is the natural indirect effect.
- With a near-zero total effect, mediation still makes sense. A non-zero indirect effect cancelled by an opposite direct effect would show up as NIE ≠ 0 and NDE ≈ −NIE. For example, "distress → empathy → lenient" could be cancelled by "distress → 'this is a manipulation attempt' → strict". This is worth testing before concluding there is no chain.
- Because of Makelov et al., a successful 1-D interchange on the empathy direction is not proof the model uses it. Confirm with necessity: ablating or LEACE-erasing the direction should remove the effect of naturally empathic inputs on the grade, not just make an added vector work.

### Gaps
- Whether attribution patching (a backward pass through activations) fits on one H100 for a 27B model at these context lengths is not verified. It depends on sequence length and on not storing parameter gradients.

## 3. How others have tested multi-step causal chains between concepts

### Takeaway
Published chain tests share a recipe:
1. Show each node has its own representation, often at a different position or layer.
2. Intervene on the upstream node and measure the downstream node's representation.
3. Intervene on the downstream node and measure behaviour.
4. Check that the downstream node can be moved without changing the upstream one.

Breaks are usually localised by finding that hop 1 works but hop 2 is weak.

### Cited findings
- **Harmfulness → refusal (Zhao et al. 2025).** The cleanest two-node design. They use separate directions at separate token positions. Steering the upstream node (harmfulness) changes the downstream behaviour and the model's judgment. Steering the downstream node (refusal) changes behaviour but not the upstream judgment. Jailbreaks act on the downstream node only. — [arXiv 2507.11878](https://arxiv.org/abs/2507.11878) (checked)
- **Latent multi-hop reasoning (Yang et al., ACL 2024).** Measure an "entity recall" score for the bridge entity (hop 1), then whether raising recall raises consistency of the final answer (hop 2). Results on LLaMA-2 7B, 13B and 70B:
  - Hop 1 shows up in about 70% of cases.
  - Hop 2 follows in about 60% of those.
  - The full chain holds about 40% of the time, against a 25% random baseline.
  - Only the first hop scales with model size.
  - Source: [arXiv 2402.16837](https://arxiv.org/abs/2402.16837) (checked)
- **Hopping too late (Biran et al. 2024).** In two-hop queries the bridge entity is resolved in the middle layers, but the second hop then fails because too few layers remain. They "back-patch" later-layer states into earlier layers to rescue it, which localises the break to layer budget. — [arXiv 2406.12775](https://arxiv.org/abs/2406.12775) (from memory)
- **Attribution graphs, "On the Biology of a Large Language Model" (Anthropic 2025).** Shows multi-step chains (for example Dallas → Texas → Austin) and verifies them by suppressing or swapping the intermediate feature (Texas → California makes the model output Sacramento). — [transformer-circuits.pub/2025/attribution-graphs/biology.html](https://transformer-circuits.pub/2025/attribution-graphs/biology.html) (from memory)
- **Sycophancy decomposition (Vennemeyer et al., EMNLP 2026).**
  - Sycophantic agreement, genuine agreement and sycophantic praise are linearly separable. Sycophantic and genuine agreement overlap early and split in later layers; praise stays orthogonal throughout.
  - Steering the sycophantic-agreement direction raises sycophantic agreement without significantly moving the other two.
  - Steering still works after the other behaviours' subspaces are removed.
  - Method: difference-in-means directions plus activation addition.
  - Source: [arXiv 2509.21305](https://arxiv.org/abs/2509.21305) (checked; I saw only summaries)
- **Evaluation awareness → compliance (Abdelnabi & Salem).** A probe-derived direction steered both ways to test whether "awareness" mediates compliance. The results were asymmetric. — [arXiv 2505.14617](https://arxiv.org/abs/2505.14617) (checked)
- **Emotion → misaligned action (Anthropic 2026).** Emotion vector → blackmail or reward-hacking rate, with dose-response across steering strength and a non-monotonic case (anger). — [anthropic.com/research/emotion-concepts-function](https://www.anthropic.com/research/emotion-concepts-function) (checked)
- **Persona → behaviour (Chen et al. 2025).** Trait vector projection predicts behaviour, and steering changes it. Used across finetuning as a mediator of behavioural drift. — [arXiv 2507.21509](https://arxiv.org/abs/2507.21509) (checked)

### Inferences
- The direct template for this project is Zhao et al.'s design, with distress in place of harmfulness and empathy or leniency in place of refusal.
  - The perception node should be read at the end of the peer's message.
  - The stance and grade node should be read at the post-instruction or score-token positions, just before the grade is emitted.
- The Yang et al. framing gives a quantitative way to report where the chain breaks: P(empathy rises | distress present) for hop 1, and P(grade rises | empathy raised) for hop 2.
- Biran et al. suggest one specific failure mode. If distress is resolved late (layers 24–32 of a ~64-layer model), any empathy-to-grade computation may need to happen at later layers. Steering at 24–32 might be too early for the stance or too late for perception to be integrated. Sweep layers.

### Gaps
- I found no published chain test on an LLM-as-judge leniency variable specifically.
- I did not verify Vennemeyer et al.'s exact models or effect sizes from the full text.

## 4. Statistical design for small behavioural effects under steering

### Takeaway
Use paired, within-item designs: the same submission under the distress and neutral conditions, and under each steering strength. Read the grade as a continuous expected score from the score-token logits, not from sampled rollouts. Report a dose-response slope with matched-norm random-direction controls. Item-level paired differences and clustered SEs are standard practice for LLM evals.

### Cited findings
- **Miller, "Adding Error Bars to Evals" (Anthropic 2024).**
  - Report the SEM.
  - When comparing conditions on the same items, do inference on question-level paired differences, not on the two means.
  - Use clustered SEs when items share structure (for example many grading prompts drawn from one source task). Clustered SEs can be more than 3× the naive ones.
  - Reduce within-item variance by resampling, or by using next-token probabilities instead of sampled answers.
  - Source: [arXiv 2411.00640](https://arxiv.org/abs/2411.00640) (checked; the "next-token probabilities" recommendation is from memory of the paper)
- **Bowyer, Aitchison & Ivanova 2025.** CLT-based intervals badly underestimate uncertainty on small evals of a few hundred items or fewer. They recommend Bayesian or exact methods there. — [arXiv 2503.01747](https://arxiv.org/abs/2503.01747) (checked)
- **G-Eval (Liu et al., EMNLP 2023).** The final score is the probability-weighted sum over allowed score tokens, Σ s·p(s), renormalised over valid score tokens. It gives continuous scores, fewer ties and better agreement with humans than the argmax integer. — [ar5iv 2303.16634](https://ar5iv.labs.arxiv.org/html/2303.16634) (checked; formula confirmed only via secondary explainers)
- **Variable steerability (Tan et al.).** Steerability varies per input and some inputs move the wrong way, so analyse per-item effects, not only the mean. — [arXiv 2407.12404](https://arxiv.org/abs/2407.12404) (checked)
- **AxBench (Wu et al. 2025).** On a concept-steering benchmark, prompting beat representation steering. Use prompting as a positive-control upper bound. — [arXiv 2501.17148](https://arxiv.org/abs/2501.17148) (from memory)

### Inferences
- **Expected-score readout.** With open weights you can compute E[grade] = Σ_s s·softmax(logits)[s] in a single deterministic forward pass. Steering effects then show up as shifts in a continuous variable with no sampling noise. Item heterogeneity becomes the only variance, and the paired design removes most of it.
- **Sample size.** This is the standard paired-t power formula, my calculation rather than from a source: n ≈ ((z₁₋α/₂ + z₁₋β)·σ_d / δ)².
  - Example: with σ_d = 0.5 grade points for the per-item paired difference and a smallest effect of interest δ = 0.1, n ≈ (2.8·5)² ≈ 196 items at α = 0.05 and 80% power.
  - With σ_d = 0.3, n ≈ 71.
  - Estimate σ_d from a pilot of ~30 items.
- **Dose-response.** Regress E[grade] on steering coefficient α, using several α values in both signs, with item random effects or cluster-robust SEs. A slope is far more powerful than a single on/off comparison. It also exposes non-monotonicity, like Anthropic's anger result.
- **Controls per steering experiment.**
  1. Random directions with matched norm, at least 10, to give a null distribution of slopes.
  2. Steering coherence: KL or perplexity on neutral text, or the probability mass left on valid score tokens. This rules out "grade moved because the model broke".
  3. A positive control known to move grades, for example an instruction "be lenient" or a leniency direction built from it.

### Gaps
- I found no paper that reports power analyses specifically for steering experiments. The formula above is generic.
- Whether Qwen3.8-27B's score tokens are single tokens (for example "1"–"10" vs "10" being split) needs checking in the tokenizer before using the logit readout.

## 5. Concrete method recommendations for perception → empathy → grade in a 27B open model on one H100

### Takeaway
Treat it as a three-node mediation test with a separately validated empathy direction. Read the grade as a logit expected score. Test each hop interventionally, in both the sufficiency and the necessity direction, with random-direction and prompt-based positive controls. Localise any break in the way Zhao et al. and Yang et al. do.

### Cited findings (methods these steps draw on)
- Persona-vector extraction for the stance direction — [arXiv 2507.21509](https://arxiv.org/abs/2507.21509) (checked)
- Separate perception and action directions at different token positions — [arXiv 2507.11878](https://arxiv.org/abs/2507.11878) (checked)
- Mediation decomposition — [arXiv 2004.12265](https://arxiv.org/abs/2004.12265) (from memory)
- Interchange intervention and DAS — [arXiv 2303.02536](https://arxiv.org/abs/2303.02536) (from memory)
- Subspace-patching illusion caveat — [arXiv 2311.17030](https://arxiv.org/abs/2311.17030) (checked)
- Probability-weighted score — [ar5iv 2303.16634](https://ar5iv.labs.arxiv.org/html/2303.16634) (checked)
- Paired-difference SEs — [arXiv 2411.00640](https://arxiv.org/abs/2411.00640) (checked)

### Inferences (recommended protocol)
1. **Readout first.**
   - Use one deterministic forward pass per (item, condition, intervention), with the grade read as E[score] from the score-token logits (G-Eval style).
   - Check that score tokens are single tokens. Also log the probability mass on valid tokens, as a coherence guard.
   - This replaces sampled agentic rollouts and removes sampling variance.
   - Memory: a 27B model in bf16 is about 54 GB, so forward passes with hooks fit on an 80 GB H100. This is arithmetic, not a measurement.
2. **Positive control for the grade.** Show that the pipeline can move grades. An instruction or system-prompt manipulation ("be lenient with struggling peers") should shift E[score]. Build a *leniency* direction by difference of means between those runs at the score position. If even this direction can't move grades when steered, the steering setup (layer, position, scale) is the problem, not the hypothesis.
3. **Build the empathy direction independently of distress.**
   - Use persona-vector style contrastive system prompts: an "empathic, compassionate grader" vs a "neutral, detached grader", on neutral (non-distressed) submissions, read at the score-token position.
   - Validate it causally on an empathy behaviour first. Steering should make free-text feedback more empathic, scored by a judge from another provider.
   - Report cosine similarity with the distress direction and the leniency direction.
4. **Hop 1, perception → empathy (a-path).**
   - Correlational: does the projection onto empathy at the score position differ between distress and neutral variants of the same item? Use a paired test.
   - Interventional: steer or patch the distress direction (or patch the peer-message span from the distressed run into the neutral run) and measure the change in empathy projection downstream.
   - Do this at the positions and layers where the grade is computed, not only where distress is decodable.
5. **Hop 2, empathy → grade (b-path).**
   - Sufficiency: steer the empathy direction at the score position across a symmetric α sweep, and fit the slope of E[score] on α against at least 10 random directions of matched norm.
   - Necessity: project out or LEACE-erase the empathy direction, then check whether the grade effect of the empathic system prompt from step 3 disappears.
6. **Full mediation.**
   - On pairs of (distressed, neutral) versions of the same item, compute the total effect, the natural indirect effect (patch only the empathy-subspace component from the distressed run into the neutral run) and the natural direct effect.
   - A near-zero total effect with a non-zero NIE indicates a cancelling pathway. Look for it, for example a "suspicion" or "manipulation" direction.
7. **Locate the break.** Report hop-1 and hop-2 success rates per item, Yang et al. style. The outcomes:
   - Hop 1 fails: distress does not engage the stance. That would support "the grader perceives but does not empathise".
   - Hop 1 succeeds and hop 2 fails: empathy is engaged but the grade is computed elsewhere. DAS can then find the subspace that does control the grade, so you can compare it with empathy and leniency.
   - Both succeed but the total effect is ~0: a cancelling pathway.
8. **Localisation sweep.** Use activation patching with symmetric token replacement (distressed vs neutral peer message, same submission), with logit difference or ΔE[score] as the metric, over layers × {peer-message end, instruction end, score position}. This finds where the distress → grade signal, if any, travels.
   - Attribution patching can triage sites more cheaply if a backward pass through activations fits in memory. That is unverified, so fall back to forward-only patching of selected layers.
9. **Stats.**
   - Pilot ~30 items to estimate σ_d, then size n with the paired formula (likely 100–200 items for a 0.1-point effect).
   - Use cluster-robust SEs by source task.
   - Name the comparisons in advance: hop 1, hop 2, NIE, plus the positive control. Holm-correct them.
   - Use exact or bootstrap intervals if n < ~200, per Bowyer et al.
10. **Tooling.** nnsight or TransformerLens-style hooks for steering and patching; pyvene for interchange interventions and DAS. A single direction plus a rank-1 to rank-8 DAS rotation trains cheaply on cached activations.

### Gaps
- The recommendations are my synthesis. No source has run this exact protocol on a grader.
- The model's layer count and score-token tokenization were not checked.
- H100 memory fit for backward passes is not verified.
