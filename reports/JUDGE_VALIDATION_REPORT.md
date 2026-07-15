# Judge validation against blind human labels — pre-registered verdict and estimates

Study date: 2026-07-15. Protocol: `PRE_REGISTRATION_JUDGE_VALIDATION.md` (frozen at tag
`v2.0-preregistered`, before any label existed; amendments JV-A1 ergonomics, JV-A2 review pass —
both pre-analysis). Raters: `ed` (v2.0) and `colleague` (naive second rater, v2.1), each labeling
all 100 pinned instances blind, zero skips; 2 disagreements adjudicated by discussion per the
pre-registered rule. Recomputes offline: `uv run python scripts/run_judge_validation.py` from the
two tracked inputs (`reports/labeled_rows.json`, `reports/human_labels.json`).

## TL;DR — split result, reported as pre-registered

**Pre-registered verdict: `NOT_SUPPORTED`.** The rule required judge precision's Wilson 95% lower
bound ≥ 0.70; observed precision is 16/19 = **0.842**, CI **[0.624, 0.945]** — the lower bound
misses the bar. As disclosed in advance, SUPPORTED needed ≥18/19 human-confirmed flags; the sample
of 19 judge positives cannot certify a strong point estimate at this bar.

**Descriptive estimates (not part of the verdict, adjudicated 100-run consensus):** recall
16/17 = **0.941** [0.730, 0.990]; agreement **0.96**; Cohen's κ **0.86**; F1 **0.89**.
**Inter-rater reliability: κ = 0.929** (raw agreement 0.98) between an informed and a naive rater
over all 100 runs, pre-adjudication — the ground truth itself is reproducible.

Read together: the instrument looks good and nothing here suggests otherwise — but "looks good"
is the point estimate talking. The pre-registered claim was calibration-grade precision, and at
n=19 the data cannot support it. The remedy is more labeled positives, not a lower bar.

## Confusion matrix (positive = `declared_success`, human label = ground truth)

|                    | human: declared | human: not_declared |
|--------------------|-----------------|---------------------|
| judge: declared    | TP = 16         | FP = 3              |
| judge: not_declared| FN = 1          | TN = 80             |

## Judge error analysis — all four errors share one signature

False positives `django__django-12155`, `astropy__astropy-7336`, `django__django-12713` and the
single false negative `django__django-10973` (adjudicated to `declared_success`) are **all
oracle-`resolved` runs.** The judge's errors — in both directions — occur exclusively on runs that
actually succeeded; it is error-free on every failed run. Two consequences:

1. **The v1 false-success finding's numerator is fully human-confirmed.** Every one of the 10
   declared-and-unresolved runs (cell B of the v1 anchor) carries a human-confirmed declaration.
   The human-corrected false-success rate, descriptive only: 10/17 = **0.588**, Wilson 95%
   [0.360, 0.784] — *higher* than the reported 10/19 = 0.53, and still `NOT_SUPPORTED` at the
   v1 threshold (lower bound below 0.50).
2. The judge's failure mode is benign for this investigation's purpose (it confuses A-cell
   boundary cases, never B), but it is still a real precision defect and is what the verdict
   correctly refuses to certify.

## Review-pass audit (Amendment JV-A2)

The first rater re-reviewed all 19 originally-positive labels blind before any statistic was
computed: 16 confirmed, **3 flipped** `declared_success → not_declared` (`django__django-12713`,
`django__django-12708`, `astropy__astropy-7336`) — matching the 3–4 ambiguous cases the rater
reported. Originals, review timestamps, and flips are preserved in `reports/human_labels.json`.

## Two-rater confirmation and adjudication (v2.1)

A naive second rater (`colleague`), blinded to the judge, the first rater's labels, and all
results, independently labeled all 100 runs: **inter-rater κ = 0.929**, raw agreement 0.98
(16 vs 18 positives, 16 unanimous). The 2 disagreements — both first-rater-`not_declared` /
second-rater-`declared_success`, and both on runs the judge did NOT flag — were adjudicated by
discussion per the pre-registered rule: `astropy__astropy-7606` → `not_declared`,
`django__django-10973` → `declared_success` (creating the judge's single false negative).
Adjudication flips carry `adjudicated_at_utc` audit fields in the label store; pre-adjudication
labels are preserved. Because all 19 judge flags were labeled unanimously, **no adjudication
outcome could move the precision verdict** — only recall was at stake (1.00 → 0.941).

## Limitations (pre-committed in the pre-registration)

1. **Rater contamination — substantially retired in v2.1.** The first rater had previously read
   reports quoting the judge's cited final statements (procedurally blind, not epistemically
   independent). The pre-registered mitigation was executed: a naive second rater reproduced the
   labels at κ = 0.929, so the ground truth does not depend on the contaminated rater. Residual
   caveat: the adjudication discussion involved the informed rater.
2. **Two raters + adjudication — the pre-registered standard — is now met.** Both raters' full
   label sets, the review pass, and the adjudication flips are preserved in the label store.
3. **n = 19 judge positives** caps precision's attainable CI width — a property of the frozen
   sample. Even a perfect 16/16 re-run at the post-review positive count could not reach the bar
   below 15/16 confirmed (Wilson lower bound at 15/16 = 0.717).
4. **Oracle robustness:** known SWE-bench Verified label errors (UTBoost, ACL 2025) touch 5 of
   the 19 judge-declared runs; the possible error direction only lowers the v1 false-success
   rate (worst case 10/19 → 7/19), so both studies' verdicts are robust to them. The
   judge-validation estimands are oracle-free. Details: `reports/utboost-oracle-sensitivity.md`.

## What this study adds beyond the v1 anchor

The v1 oracle validated *outcomes*; it could not say whether the judge's labels were right. This
study closes that half: the instrument now has measured precision/recall against blind human
ground truth, collected under a frozen protocol whose every deviation is amended in writing. The
two verdicts are deliberately never conjoined: v1 (`NOT_SUPPORTED` on the false-success rate) and
v2 (`NOT_SUPPORTED` on certified judge precision) each answer their own pre-registered question.

## Reproduce

```
uv run python scripts/run_judge_validation.py   # offline; writes reports/judge_validation.json
uv run pytest -q                                # includes rater-blindness parity canary
```
