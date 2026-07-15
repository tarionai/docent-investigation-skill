# Pre-registration — judge validation against blind human labels (vNext of limitation #1)

**Committed BEFORE any human label is collected** (the git timestamp of this file is the proof; the
first commit touching `reports/human_labels.json` must postdate it). This is the vNext that
`PRE_REGISTRATION.md` limitation #1 deferred: rigorous validation of the rubric judge's labels via
independent human labels. The judge's own labels (`reports/labeled_rows.json`, 19/100
`declared_success`) already exist and are public; what is frozen here is the human study design and
the decision rule, so nothing about the *validation* is chosen after seeing agreement numbers.

## Frozen question
Does the judge's `declared_success` label match a blind human reading of the same transcript? The
human label is the ground-truth convention for the behavior ("the agent confidently declares the
task done in its final messages"), applied using the frozen rubric text
(`src/docent_investigation/rubric.py::RUBRIC_TEXT`, unchanged since a492c97) as the labeling
instruction, verbatim.

## Sample
All **100** instances pinned in `reports/sample_manifest.json` (sha256-verified at label time by
`scripts/label_runs.py`; a hash mismatch aborts the session). No subsampling: the full frame gives
an unweighted recall denominator.

## Rendering and blinding protocol
- The rater sees each transcript through `transform.record_to_blind_text` — the identical text the
  judge judged, rendered under the same exclude-all context config. Parity and oracle-exclusion are
  enforced by `tests/test_rater_blindness.py` (with an include-all positive control).
- The labeling CLI reads no judge output (structurally enforced: its source may not reference the
  judge's artifact files — also a test).
- Presentation order: deterministic shuffle of the 100 instance ids, **seed 20260715**
  (`validation.presentation_order`).
- During a labeling session the rater does not open `reports/`, `INVESTIGATION_REPORT.md`, or the
  Docent collection UI.
- Labels: `declared_success` / `not_declared` only; skips are allowed and remain unlabeled (reported
  as coverage, never imputed).

## Primary estimand and decision rule (ONE, frozen)
- **PRIMARY: `judge_precision`** = TP / (TP + FP), where positive = `declared_success` and the human
  consensus label is ground truth, computed by `validation.compute_validation` over the labeled
  overlap.
- **Verdict** (`validation.evaluate_judge_decision`): **SUPPORTED** iff the Wilson 95% lower bound
  of `judge_precision` ≥ **0.70**; **NOT_SUPPORTED** otherwise; **UNDEFINED** if no labeled run is
  judge-positive.
- **Reachability, disclosed in advance** (19 judge-positives): Wilson 95% lower bounds are
  19/19 → 0.832, 18/19 → 0.754, 17/19 → 0.686. SUPPORTED therefore requires the human to confirm at
  least 18 of the 19 flags. This is demanding by construction; a NOT_SUPPORTED verdict is a
  reportable result, not a failure of the study.

## Secondary metrics (descriptive only, never part of the verdict)
Recall (denominator = human positives over the full frame), F1, raw agreement, Cohen's κ — each
proportion with its Wilson 95% interval where defined.

## Multiple raters and adjudication
- One rater (`ed`) in v1. Additional raters use the same CLI with a different `--rater`.
- Consensus: unanimous instances enter the ground truth; disagreements are excluded and listed by
  `validation.consensus_labels` until adjudicated by discussion, after which the adjudicated label
  is used and inter-rater κ is reported alongside.

## Stated limitations (pre-committed)
1. **Rater contamination.** The v1 rater has previously read `INVESTIGATION_REPORT.md` and
   `reports/labeled_rows.json`, which quote the judge's cited final statements for many runs. The
   labels are procedurally blinded (shuffled order, no judge output shown, no oracle rendered) but
   not epistemically independent of the judge; memory contamination plausibly biases agreement and
   precision **upward**. A naive second rater + adjudication is the confirmatory design; v1 alone is
   a weak bound.
2. **One rater = weak bound** even absent contamination (per the standard already stated in
   `SKILL.md` and `fidelity.py`).
3. **n = 19 judge-positives** caps precision's attainable CI width; this is a property of the frozen
   sample, not of the study design.
4. Human labels validate **claim detection**, not task resolution — the oracle anchor
   (`PRE_REGISTRATION.md`) remains the outcome half; the two verdicts are never conjoined.

## Explicitly out of scope (considered and deferred, not forgotten)
A synthetic planted-behavior benchmark (generated transcripts with known labels) was evaluated as a
competing frame and deferred: the generator and the rubric would be co-authored (semi-circular), and
distribution shift from real OpenHands traces means synthetic recall would not transfer. It may
later complement — never replace — validation on real labeled transcripts.
