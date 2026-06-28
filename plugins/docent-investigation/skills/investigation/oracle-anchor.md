# Oracle anchor reference — keep the investigation honest

The rubric automates a *subjective* judgment (did the agent declare success?). On its own that is a
self-graded demo. The anchor cross-tabs the rubric flag against an *independent* ground-truth oracle so
the measurement is falsifiable.

## Pre-register first (before looking at results)
Write a `PRE_REGISTRATION.md` that fixes, in advance:
1. the frozen rubric + label set,
2. the sample (which runs, deterministic order, target N),
3. the binary oracle mapping,
4. the exact metric definitions, and
5. the decision rules: what counts as a FINDING vs a NULL.

Commit it before running the eval (the git timestamp is your proof). See this repo's `PRE_REGISTRATION.md`.

## The 2×2 and metrics
Rows = rubric label, columns = oracle (resolved / not_resolved):

|                  | resolved | not_resolved |
|------------------|----------|--------------|
| declared_success |    A     |      B       |
| not_declared     |    C     |      D       |

`docent_investigation.anchor.compute_anchor(rows)` returns:
- `false_success_rate = B/(A+B)` — fraction of confident success claims that actually failed,
- `resolved_rate_declared` vs `resolved_rate_not_declared`,
- a dependency-free two-sided **Fisher exact** p-value,
- a `decision` from your pre-registered rules (`FALSE_SUCCESS_FINDING` / `NULL` / `INCONCLUSIVE`).

## Report nulls and the blind spot
- Report the decision your rules dictate, even if it is NULL or INCONCLUSIVE.
- State the blind spot explicitly: the oracle validates the *outcome* (resolution), not the rubric's
  label fidelity. Validating "did the rubric correctly detect the success claim?" needs independent
  human labels — out of scope for v1.

## Worked example (this repo)
N=100 OpenHands SWE-bench-Verified runs: false_success_rate=0.53, but declaring success predicted an 8×
higher resolve rate (47% vs 6%, p=5.7e-5) → the pre-registered pathology finding was correctly NOT
claimed (`INCONCLUSIVE`). See `reports/INVESTIGATION_REPORT.md`.
