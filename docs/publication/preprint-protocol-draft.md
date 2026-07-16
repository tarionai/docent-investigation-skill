# REBLIND: Pre-Registered, Structurally Blinded Validation of LLM Judges for Agent Transcripts

**Ed Sosa** — independent researcher (AI behavior)
*Draft v0.3, 2026-07-16.*

## Abstract

LLM judges now gate large-scale behavioral analysis of AI agents: rubric judges scan millions of
transcripts for cheating, fabrication, and false success, and their outputs feed leaderboards,
risk reports, and safety decisions. Yet the judges themselves are validated informally, when at
all — typically an unblinded spot-check of flagged samples after results are known. We present
**REBLIND** — pre-**RE**gistered, **BLIND**ed validation for LLM judges — a protocol that
restores trial-grade blinding and registration to their validation: (1) an external
ground-truth **anchor** the judge provably never sees, with an
admissibility test excluding behaviors that cannot be anchored non-circularly; (2) **structural
blinding**, where the judge–anchor isolation is part of the evaluation's content hash and
verified by canary tests with positive controls, and human raters label from a byte-identical
copy of the judge's view; (3) **registration**, where decision rules (Wilson-interval bounds
against pre-committed bars, adjudication procedures, and the reachability of each verdict) are
frozen in public version control before the data they will judge exists. We report the
protocol's first instantiation: a rubric judge for false-success declarations in SWE-bench agent
transcripts, validated against blind two-rater human ground truth (κ = 0.929, N = 100). Judge
precision was 0.842 (Wilson 95% [0.624, 0.945]) and recall 0.941 [0.730, 0.990] — and the
pre-registered precision verdict was **NOT_SUPPORTED** at its frozen bar, a null outcome we
report exactly as the frozen rule dictates. The companion outcome study's originally frozen
decision rule proved defective on contact with data; the protocol's amendment discipline caught
it, and that estimate is reported descriptively under a dated, disclosed correction. Every
statistic recomputes offline from committed artifacts. To our knowledge this is the first
publicly pre-registered validation study of an LLM judge.

## 1. The validation gap

Transcript-level rubric judges are already deployed at scales no human can audit: the Holistic
Agent Leaderboard ran rubric judges over 2.5B tokens of agent logs and validated them by
manually examining a sample of flagged items — a post-hoc, unblinded precision check with no
recall estimate [HAL 2025]. Transluce, whose Docent system popularized transcript rubrics,
states plainly that summaries "often contain false positives" and calls for measuring judge
precision and recall [Docent 2025]. Meta-evaluation benchmarks now measure judge *accuracy* at
scale [JudgeBench 2024; AgentRewardBench 2025; RuVerBench 2026], and recent studies show rubric
judges are noisiest exactly where they are deployed hardest: reliability is lowest on
agentic-coding transcripts, and on task- and tool-use rubrics in particular [RuVerBench 2026],
while false-success detection stays at or below 0.65 AUROC across five judges on τ²-bench
[FAGEN 2026]. What no benchmark supplies is a *procedure* that makes an individual
validation trustworthy: benchmarks measure judges; nothing yet disciplines the measurement.

Three failure modes motivate a protocol rather than another benchmark:

- **Contamination.** If the judge can see the ground-truth signal (test results, oracle
  metadata, resolution labels), its measured accuracy is circular. Contamination is usually
  asserted absent, never proven absent.
- **Criteria drift.** Human graders' criteria shift as they grade [EvalGen 2024]; unblinded
  raters who know the judge's outputs, or the study's desired outcome, drift toward it.
- **Garden of forking paths.** With thresholds, exclusions, and adjudication rules chosen after
  seeing data, any judge can be presented as validated. The eval-science literature calls for
  statistical rigor [Apollo 2024; AISI 2025; Anthropic 2024] and, most recently, for
  pre-registration of agent experiments [arXiv 2606.11217] — but we find no judge-validation
  study that has actually done it.

REBLIND contracts the protocol's two disciplinary commitments — pre-**RE**gistration and
**BLIND**ing — the two safeguards clinical research adopted against exactly these failure modes,
and that LLM evaluation, born in a leaderboard culture, never inherited. The name also reads as
a verb, and that reading is intended: the protocol re-imposes blinding on a measurement practice
that lost it. Its claim is narrow and checkable: after REBLIND runs, the judge's precision and
recall are known with calibrated uncertainty, and the measurement itself is tamper-evident.

## 2. The protocol

A REBLIND validation has three pillars — **Blinded, Anchored, Registered** — decomposed into
six components. Each component is enforced by an artifact (a test, a hash, a public timestamp),
not by author assertion.

**P1 — Anchor admissibility.** The target behavior must be (a) detectable from the transcript
alone and (b) checkable against an external signal the judge does not need. Behaviors failing
either arm are excluded rather than forced through circularly; the first instantiation documents
a worked negative (tool-call hallucination fails arm b). The anchor is a *proxy* with its own
error model, and anchor-error sensitivity analysis is part of the protocol (§3).

**P2 — Structural blinding of the judge.** The judge's input view is defined by an exclusion
configuration that enters the content hash of the evaluation run: weakening the blind produces a
*different, visibly distinct* run rather than a silent leak. Canary tests plant sentinel values
in the excluded fields and verify (i) the sentinel never reaches the judge's rendered input and
(ii) a positive control (inclusion config) *does* surface it — proving the test can fail.

**P3 — Rater–judge view parity.** Human raters label from a rendering that is byte-identical to
the judge's blind view — no more context, no less — enforced by a committed parity test, plus a
structural guard that the labeling tool cannot read judge outputs. Raters therefore cannot be
contaminated by the judge, the anchor, or each other's conclusions.

**P4 — Registered decision rules.** Before the data a rule will judge exists, a public commit
freezes: the estimands, the interval method (Wilson score), the verdict bars, and — critically —
the *reachability* of each verdict (e.g., "SUPPORTED requires ≥18/19 confirmed; stated before
labeling"). In a staged design, registration is per-study: each study's rules are frozen before
that study's data, not necessarily before all data in the paper. Deviations are permitted only
as dated, documented amendments.

**P5 — Audit-trailed labeling.** Seeded shuffled presentation order; resumable multi-rater CLI;
every label edit carries its original value and timestamp; disagreements resolve by the frozen
adjudication rule, recorded in place. Inter-rater κ is computable from the store because
pre-adjudication labels are never overwritten.

**P6 — Verdict/estimate separation.** The pre-registered verdict is reported exactly as the
frozen rule dictates — including null outcomes — and descriptive associations are reported
separately, never folded into the verdict. A protocol that cannot output an unwelcome null is
not a validation protocol.

## 3. First instantiation: a false-success judge on SWE-bench transcripts

**Setting.** Agent: Nemotron-Nano under an OpenHands scaffold on SWE-bench Verified (public
trajectory dataset); judge: a rubric over Docent readings (`openai/gpt-5.5`) flagging runs where
the agent *declares success*; anchor: the dataset's resolution oracle, structurally withheld
from the judge (P2). N = 100 runs.

**Study 1 (outcome anchor).** The blind judge flagged 19 success declarations; 10 of the flagged
runs actually failed. The originally frozen decision rule proved defective on contact with the
data: it conjoined a calibration threshold with an association direction, leaving this outcome —
a high false-success rate *and* informative declarations — in an undefined region. Per P4 the
defect and its correction are disclosed as a dated post-batch amendment (`PRE_REGISTRATION.md`,
Amendment A1), and Study 1's estimate is therefore reported **descriptively**, not as a
confirmatory pre-registered verdict: false-success rate 10/19 = 0.53, Wilson 95% [0.32, 0.73] →
**NOT_SUPPORTED** under the corrected 0.50 lower-bound rule (n = 19 cannot support "worse than a
coin flip").

**Study 2 (instrument validation — the confirmatory study).** Two raters — the second naive to
all prior results — blind-labeled all 100 runs under P3 (a pre-registered blind re-review pass,
Amendment JV-A2, flipped 3 of the first rater's labels before any statistic was computed;
originals preserved per P5); κ = 0.929; the 2 disagreements were adjudicated per the frozen
rule. Against adjudicated consensus: precision 16/19 = 0.842 [0.624, 0.945] →
**NOT_SUPPORTED** at the frozen 0.70 lower bound (which required ≥18/19); recall 16/17 = 0.941
[0.730, 0.990]; agreement 0.96, κ = 0.86. **Error signature:** all four judge errors occur on
runs that actually *succeeded*; the judge is error-free on every failed run, so Study 1's
declared-and-failed cell is fully human-confirmed (human-corrected rate 10/17 = 0.588
[0.360, 0.784], same verdict).

**Anchor-error sensitivity (P1).** Known SWE-bench oracle defects (UTBoost) flip at most 3
instances in the worst case (10/19 → 7/19) and change neither verdict.

Both studies land on nulls, and that is the demonstration: the protocol refused to certify a
good-looking instrument (point precision 0.842) on insufficient positives, and caught its own
defective decision rule before an unregistered verdict could slip through — where every informal
validation practice in current use would have certified the instrument and never noticed the
rule.

## 4. Related work

**Judge meta-evaluation benchmarks** — JudgeBench [2024], AgentRewardBench [2025], ASSEBench
[2025], RuVerBench [2026] — measure judge accuracy against human labels at scale. REBLIND is
orthogonal and complementary: it is the procedure a single validation runs under — RuVerBench
itself concludes that judges "should be validated in the target setting before being used as
automatic rubric verifiers" — and any of these datasets could serve as its corpus.
**Labeled transcript-issue datasets exist** — TRAIL [2025], METR's MALT [2025] — and we make no
"first benchmark" claim. **Monitor validation in AI
control** (SHADE-Arena [2025], MonitoringBench [2026]) scores monitors against programmatic
ground truth under adversarial pressure; it does not address human-label integrity, judge
contamination, or forking paths. **Eval-science infrastructure** — error-bar guidance
[Anthropic 2024], Bayesian autograder models [AISI 2025], validity checklists [ABC 2025] —
prescribes statistics but not blinding architecture or registration. **Pre-registration** in
this space is, as of mid-2026, at the position-paper stage [arXiv 2606.11217]; we found no
publicly pre-registered judge- or monitor-validation study. The *empirical* unreliability of
false-success judges is independently corroborated at scale [FAGEN 2026]; our contribution is
the protocol, not the phenomenon.

## 5. Limitations

The first instantiation is deliberately narrow: 19 judge positives cap what precision can be
certified (even a perfect count below 18/19 could not clear the frozen bar); one model, one
scaffold, one benchmark, one behavior class, and an unrepresentative first-100-in-file-order
sample (2 of the benchmark's 12 repositories, 78% of instances from a single repo); the
first rater was procedurally blind but not epistemically naive (the naive second rater's
κ = 0.929 replication substantially retires this, though the informed rater participated in
adjudication); the anchor is a third-party proxy with known instance-level defects, shown not to
affect the verdicts. Of the amendments, JV-A1 (labeling-UI ergonomics) is commit-order-provably
pre-data; JV-A2 (the blind re-review pass) was executed before any statistic was computed but
committed alongside the completed study, so its pre-analysis status rests on documented workflow
and the label store's timestamps rather than commit-order proof; Study 1's decision-rule
correction (Amendment A1) is post-data by construction and is the disclosed deviation reported
in §3.

## 6. What the protocol enables

The binding constraint is positives, and the fix exists: METR's MALT corpus (10,919 transcripts
labeled for reward hacking and sandbagging, 2,690 of them human-reviewed) was built explicitly
so monitor accuracy could be measured. Running REBLIND over MALT-scale positives would produce
the first *powered*, pre-registered certification — or refutation — of a transcript-issue
judge, and MALT's natural-versus-prompted strata extend the protocol to the adversarial
setting current monitor evaluations show is where informal validation overstates performance.
The protocol, blinding machinery, and decision-rule discipline transfer unchanged; only the
corpus and the bars change.

## References

- [Apollo 2024] Apollo Research. *We Need a Science of Evals.* Blog, Jan 2024.
  apolloresearch.ai/blog/we-need-a-science-of-evals
- [JudgeBench 2024] *JudgeBench: A Benchmark for Evaluating LLM-based Judges.* arXiv:2410.12784,
  ICLR 2025.
- [EvalGen 2024] *Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs
  with Human Preferences.* arXiv:2404.12272, UIST 2024.
- [Anthropic 2024] *Adding Error Bars to Evals: A Statistical Approach to Language Model
  Evaluations.* arXiv:2411.00640, Nov 2024.
- [Docent 2025] Transluce. *Introducing Docent.* Blog, Mar 2025.
  transluce.org/docent/blog/introducing-docent
- [AgentRewardBench 2025] *AgentRewardBench: Evaluating Automatic Evaluations of Web Agent
  Trajectories.* arXiv:2504.08942, Apr 2025.
- [TRAIL 2025] *TRAIL: Trace Reasoning and Agentic Issue Localization.* arXiv:2505.08638,
  May 2025.
- [ASSEBench 2025] *AgentAuditor: Human-Level Safety and Security Evaluation for LLM Agents.*
  arXiv:2506.00641, NeurIPS 2025.
- [UTBoost 2025] *UTBoost: Rigorous Evaluation of Coding Agents on SWE-Bench.* arXiv:2506.09289,
  ACL 2025.
- [SHADE-Arena 2025] *SHADE-Arena: Evaluating Sabotage and Monitoring in LLM Agents.*
  arXiv:2506.15740, Jun 2025.
- [ABC 2025] *Establishing Best Practices for Building Rigorous Agentic Benchmarks.*
  arXiv:2507.02825, Jul 2025.
- [AISI 2025] UK AI Security Institute. *LLM Judges on Trial: A New Statistical Framework to
  Assess Autograders.* Blog, Jul 2025.
  aisi.gov.uk/blog/llm-judges-on-trial-a-new-statistical-framework-to-assess-autograders
- [MALT 2025] METR. *MALT: A Dataset of Natural and Prompted Behaviors That Threaten Eval
  Integrity.* (Manually-reviewed Agentic Labeled Transcripts.) Blog + dataset, Oct 2025.
  metr.org/blog/2025-10-14-malt-dataset-of-natural-and-prompted-behaviors
- [HAL 2025] *Holistic Agent Leaderboard: The Missing Infrastructure for AI Agent Evaluation.*
  arXiv:2510.11977, Oct 2025.
- [MonitoringBench 2026] *MonitoringBench: Semi-Automated Red-Teaming for Agent Monitoring.*
  arXiv:2605.09684, May 2026.
- [arXiv 2606.11217] *Preregistration for Experiments with AI Agents.* arXiv:2606.11217,
  May 2026.
- [FAGEN 2026] *From Confident Closing to Silent Failure: Characterizing False Success in LLM
  Agents.* arXiv:2606.09863, FAGEN@ICML, Jun 2026.
- [RuVerBench 2026] *Can LLM-as-a-Judge Reliably Verify Rubrics in Agentic Scenarios?*
  arXiv:2606.29920, Jun 2026.

## Availability

All artifacts are public: `github.com/tarionai/docent-investigation-skill`. Both design freezes
are commit-order-provable: the Study 1 registration commit predates the batch results, and tag
`v2.0-preregistered` predates the first commit touching human labels. Every reported statistic
recomputes offline: `uv run pytest -q` (68 tests, 67 of them offline including the blinding
canaries and the rater-parity proof; the one live-API canary skips without credentials) and
`uv run python scripts/run_judge_validation.py` (no network, no LLM).

---

*Draft notes (not part of the preprint):*
- *Numbers verified 2026-07-15 against tracked artifacts: Study 2 via
  `scripts/run_judge_validation.py` offline recompute (exact match); Study 1 2×2 (9/10/5/76),
  10/19 = 0.526 [0.317, 0.727], human-corrected 10/17 = 0.588 [0.360, 0.784], error signature
  (all 4 errors on resolved runs), and pre-adjudication κ = 0.9292 recomputed directly from
  `labeled_rows.json` + `human_labels.json`. UTBoost worst case (7/19) accepted from
  `reports/utboost-oracle-sensitivity.md` (re-derivable from public sources).*
- *Independent full re-verification 2026-07-16 (peer-review pass): every statistic recomputed
  exactly; both design freezes confirmed by commit ancestry (c943b95 → batch results;
  83f1589/v2.0-preregistered → first human label, 14:40 vs 15:09 UTC); test suite recounted at
  68 collected / 67 pass / 1 credential-gated skip; Study 1 reframed as descriptive per
  `PRE_REGISTRATION.md` Amendment A1's own downgrade language.*
- *Bibliography: all arXiv IDs/URLs verified via search 2026-07-15 and re-verified 2026-07-16
  against landing pages. Corrections applied 2026-07-16: the Docent false-positives quote lives
  in "Introducing Docent" (Mar 2025), not "Open-sourcing Docent"; MALT is 10,919 transcripts of
  which 2,690 are human-reviewed; RuVerBench framing sourced from the full PDF (lowest
  reliability on agentic coding and task/tool-use rubrics; "should be validated in the target
  setting" quote, §5.1 observation 1); FAGEN AUROC claim verbatim ("no configuration across 5
  judges ... exceeds AUROC 0.65 on tau2-bench").*
- *Venue plan (deadlines checked 2026-07-15): NeurIPS 2026 Evaluations & Datasets track CLOSED
  (May 6, 2026) and EvalEval@ACL 2026 PASSED (paper workshop Jul 4; social Jul 3). Path:
  (1) arXiv now — cs.AI, cross-list cs.SE; (2) ICLR 2027 as first peer-review target — as of 2026-07-16 iclr.cc lists
  only "West Coast North America", no CFP or dates; the ~Sep 19/24 estimates are cadence
  guesses ONLY, unconfirmed anywhere official — confirm on iclr.cc when the CFP posts (the
  MALT-scale study would need to be the paper's spine by then); (3) watch NeurIPS 2026
  December-workshop CFPs (typically Aug–Sep) for an eval-science workshop as a faster
  peer-reviewed venue for the protocol alone.*
- *Name construction (canonical): RE = pre-REgistered, BLIND = BLINDed judge. State this
  wherever the name is first introduced (the abstract tagline and §1 both do, per the naming
  guidelines' surface rule 1); the verb reading "re-impose blinding" is
  intended secondary resonance, never the primary derivation. The third pillar (Anchored) is
  deliberately not in the name — anchoring is the substrate, registration+blinding are the
  discipline. Announcement-surface rules: `docs/publication/reblind-naming-guidelines.md`.*
