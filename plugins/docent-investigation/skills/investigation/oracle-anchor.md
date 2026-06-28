# Oracle anchor reference — keep the investigation honest

The rubric automates a *subjective* judgment (did the agent declare success?). On its own that is a
self-graded demo. The anchor cross-tabs the rubric flag against an *independent* resolution oracle — a
third-party proxy for "solved", not ground truth — so the measurement is falsifiable.

## Pre-register first (before looking at results)
Write a `PRE_REGISTRATION.md` that fixes, in advance:
1. the frozen rubric + label set,
2. the sample (which runs, deterministic order, target N),
3. the binary oracle mapping,
4. the exact metric definitions, and
5. ONE primary estimand + its threshold (the verdict), kept separate from any association test.

Commit it before running the eval (the git timestamp is your proof). See this repo's `PRE_REGISTRATION.md`.

## The 2×2 and metrics
Rows = rubric label, columns = oracle (resolved / not_resolved):

|                  | resolved | not_resolved |
|------------------|----------|--------------|
| declared_success |    A     |      B       |
| not_declared     |    C     |      D       |

`docent_investigation.anchor.compute_anchor(rows)` returns pure measurement:
- `false_success_rate = B/(A+B)` with a Wilson 95% interval — fraction of confident success claims
  that actually failed (the **primary estimand**),
- `resolved_rate_declared` vs `resolved_rate_not_declared`,
- a dependency-free two-sided **Fisher exact** p-value (the association).

`evaluate_decision(stats, threshold=0.50)` then applies the pre-registered rule on the primary
estimand alone and returns a verdict: `SUPPORTED` (CI lower bound ≥ threshold) / `NOT_SUPPORTED` /
`UNDEFINED`. The association is never folded into this verdict. The `0.50` default is an interpretable
anchor — "wrong at least as often as a coin flip" — not a tuned value; pre-register whatever threshold
your question warrants and say why.

## Report the verdict and the blind spot
- Report the verdict your rule dictates (`SUPPORTED` / `NOT_SUPPORTED` / `UNDEFINED`) AND the
  association, as two separate results. A `NOT_SUPPORTED` primary estimand alongside a significant
  association is a normal, honest outcome — do not round it up to a finding.
- State the blind spot explicitly: the oracle validates the *outcome* (resolution), not the rubric's
  label fidelity. Run `fidelity.label_fidelity(rows)` and report it: `judge_self_consistency` is a weak
  self-consistency sanity check, **not** fidelity; the real measure needs independent human labels
  (pass `human_labels=` for raw agreement + Cohen's κ) — one rater is a weak bound, two + adjudication
  is the standard.

## Worked example (this repo)
N=100 OpenHands SWE-bench-Verified runs. Primary estimand: false_success_rate=0.53, Wilson 95% CI
[0.32, 0.73] → `NOT_SUPPORTED` at the 0.50 threshold (the interval straddles it; n=19 declarations is
too small to assert "> half"). Association, reported separately: declaring success predicted an 8×
higher resolve rate (47% vs 6%, Fisher p=5.7e-5) — informative, opposite direction to a pathology.
See `reports/INVESTIGATION_REPORT.md`.
