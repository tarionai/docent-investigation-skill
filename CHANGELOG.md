# Changelog

Notable changes to `docent-investigation-skill`, newest first. Dates are UTC. Older entries are
preserved, not edited — corrections are recorded as new entries.

## 2026-07-15 — Judge validation becomes the primary product (step-6 inversion)

The pipeline's sidecar label-fidelity check is promoted to the deliverable: the rubric judge is now
measured against blind human ground-truth labels, answering the "robust validated judges" gap named
in `reports/transluce-priorities-and-gaps.md` (Gap 1). The oracle anchor is unchanged and becomes
the outcome half of a two-sided validation.

### Added
- `validation.py` (pure): judge-vs-human confusion matrix, precision/recall with Wilson 95%
  intervals, F1, agreement, Cohen's κ; pre-registered verdict on ONE primary estimand
  (`judge_precision`, SUPPORTED iff Wilson lower bound ≥ 0.70); deterministic seeded labeling order;
  multi-rater consensus with adjudication list.
- `transform.record_to_blind_text`: renders a raw trace exactly as the blind judge sees it — the
  rater's view, built with no oracle argument so no oracle field exists to leak.
- `scripts/label_runs.py`: resumable blind labeling CLI (sole writer of `reports/human_labels.json`;
  sha256-verifies each record against the pinned manifest; reads no judge output — enforced by test).
- `scripts/run_judge_validation.py`: offline, cold-clone-reproducible runner (sole writer of
  `reports/judge_validation.json`); also feeds the human labels back through `label_fidelity` so the
  original sidecar finally reports real agreement.
- `PRE_REGISTRATION_JUDGE_VALIDATION.md`: frozen before any label is collected — sample (all 100
  pinned instances), rater protocol (seed 20260715), primary estimand with a disclosed reachability
  table (SUPPORTED requires ≥18/19 human-confirmed), adjudication rule, and the rater-contamination
  limitation named up front. `PRE_REGISTRATION.md` gains a one-line Amendment A2 pointer.
- `tests/test_rater_blindness.py`: parity canary (rater text == blind judge text, oracle sentinel in
  neither, include-all positive control) plus a structural guard on the CLI source.
  `tests/test_validation.py`: stats, decision boundaries (18/19 vs 17/19), κ/agreement parity.

### Changed
- `fidelity._cohen_kappa` promoted to public `cohen_kappa` (now shared with `validation.py`).

## 2026-07-10 — Migrate evaluation to Docent's Readings API (Analysis Plans)

Transluce no longer recommends rubric refinement as the primary workflow, so evaluation now runs on
the Readings surface (`client.query` + `client.read`), which submits a native analysis plan. The
measurement layer (anchor, fidelity, pre-registration semantics) is unchanged. Historical reports and
`PRE_REGISTRATION.md` describe the reference run as executed and are not edited.

### Changed
- `DocentClientAdapter`: `create_rubric` / `start_rubric_eval_job` / `get_rubric_run_state` /
  `wait_for_verdicts` replaced by `evaluate_rubric()` — one DQL step + one blind reading per run,
  programmatic approval (`flush(auto_approve=True)`), blocks until verdicts land, returns
  `(reading_id, verdicts)`. Resume via `verdicts_from_reading()`; `run_investigation.py` gains
  `--model` and `--reading-id` (replacing `--rubric-id`).
- Blindness invariant: `include_metadata=False` replaced by an explicit exclude-all
  `AgentRunContextConfig` (`blind_run_context()`) on the judge's agent-run parameter. Stronger than
  the old flag: exclude-all is both the SDK default and pinned by the adapter, and the config enters
  the reading's content hash — weakening it produces a visibly different reading, not a silent leak.
- `rubric.py` decoupled from `docent.judges`: the rubric is a local frozen `RubricSpec` (same frozen
  text/labels/schema); the judge model is now explicit (`DEFAULT_JUDGE_MODEL = "openai/gpt-5.5"`) and
  recorded in `results.json` as part of the instrument's identity.
- M1 canary ported: the offline render check is unchanged (readings use the same rendering layer);
  the live check runs through `evaluate_rubric`; a new tripwire test asserts the SDK's default
  context config still excludes every metadata scope, so an upstream default flip fails the suite.

### Added
- Bounded retry for the server's fresh-collection statement timeout (DQL on a just-ingested
  collection 400s for its first ~30s; observed and measured 2026-07-10). Only that specific error
  retries; anything else re-raises immediately.

### Verified
- 34 tests pass including the LIVE canary against docent.transluce.org: the judge echoed the
  message-content sentinel and never surfaced the `metadata.scores` oracle sentinel through the new
  reading path.

### Resolved (was open in the 2026-06-29 entry)
- Docent-native Analysis Plan view: evaluation now submits a native analysis plan visible in the
  collection's web UI.

## 2026-06-29 (later) — Citation audit, convergence remediation, metadata-leak canary

### Added
- **`include_metadata` leak canary** (`tests/test_metadata_canary.py`): deterministic (offline) +
  live (skipif no `DOCENT_API_KEY`). Verifies the oracle in `metadata.scores` never reaches the judge.
  Finding: the exclusion is **structural, not flag-dependent** — `AgentRunContextConfig` defaults every
  metadata filter to `EXCLUDE_ALL`, and the judge did not surface `metadata.scores` even under
  `include_metadata=True`.

### Changed
- Report hardened from a five-pass convergence review: corrected the corrupt-success construct (it is
  conditioned differently than `P(not_resolved | declared_success)`); reframed the decision-rule
  robustness claim to "no uncertainty-respecting rule returns `SUPPORTED`"; added repository
  stratification (the 8× association holds within both astropy and django — not repo-confounded);
  retitled the construct as *reliability* of self-reported completion (not probabilistic calibration);
  added conditional-metric notation distinct from the conventional false-positive rate; framed
  reproducibility as three explicit layers.

### Verified
- All 14 arXiv citations checked against live source (title + first author + topic; zero
  hallucinations); both load-bearing numbers verified against the paper bodies.

### Resolved (was open in the earlier 2026-06-29 entry)
- The `include_metadata=False` canary now exists.

### Still open
- Judge label fidelity (human Cohen's κ); second-judge robustness run; repo-stratified resample to grow
  declared-n; Docent-native Analysis Plan view; public-collection anon-viewability.

## 2026-06-29 — Method boundary, provenance, and offline reproducibility

### Added
- **Admissibility test** in `SKILL.md` step 1: a behavior is oracle-anchorable only if it is
  (1) transcript-detectable and (2) checkable against an oracle external to and withheld from the
  judge — with a worked negative example (tool-call hallucination fails (2)). The human-label fallback
  is a *fidelity study*, not oracle anchoring.
- **Oracle-provenance disclosure** in the report: the `resolved` labels are a third-party resolution
  proxy read from the dataset's published eval output (not an authors-run harness), and `resolved ≠
  correct` is documented with citations (arXiv:2503.15223, 2506.09289, 2410.06992).
- **Related work & positioning**: frames the target as *calibration of self-reported task completion
  in coding agents*, distinguished from reward hacking and sycophancy.
- **Sample-composition disclosure**: the N=100 file-order slice is 22 astropy + 78 django — 2 of the
  benchmark's 12 repos.
- `reports/labeled_rows.json`: de-identified per-run rows, so the 2×2 + verdict recompute offline
  without the live judge.
- 0.50-threshold rationale (coin-flip interpretability); `README` status updated to the completed
  N=100 run.

### Open (tracked, not yet addressed)
- Judge label fidelity is unvalidated — no human Cohen's κ; a second-judge robustness run is pending.
- No `include_metadata=False` canary integration test yet.
- Analysis runs in Python; no Docent-native Analysis Plan view yet.
- Public Docent collection anon-viewability is unverified — verify in a private window before relying
  on it as open. Reproduction does not depend on it.

## 2026-06-28 — Initial build (N0–N6) + worked N=100 run

- Marketplace/plugin scaffold + local plugin-sanity harness (fail-closed, secrets-forbidding).
- Pure OpenHands-trace → Docent `AgentRun` transform; typed Docent client adapter; frozen
  false-success-declaration rubric.
- Pre-registration committed **before** the batch (`PRE_REGISTRATION.md`, commit `c943b95`).
- Live N=100 investigation (Nemotron-Nano on SWE-bench Verified): false-success rate 0.53,
  Wilson 95% CI [0.32, 0.73] → `NOT_SUPPORTED` at the 0.50 threshold; association Fisher
  p = 5.7e-5 (declared success predicts an 8× higher resolve rate).
- `investigation` skill prose + worked report (`reports/INVESTIGATION_REPORT.md`).
