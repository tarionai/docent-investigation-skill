# UTBoost oracle-sensitivity check — the v1 verdict is robust to known SWE-bench label errors

Check date: 2026-07-15. Question: do the publicly documented SWE-bench Verified labeling errors
(UTBoost, arXiv 2506.09289, ACL 2025) affect this repo's oracle — the `resolved` labels behind the
N=100 false-success anchor (`PRE_REGISTRATION.md`)? The judge-validation study
(`PRE_REGISTRATION_JUDGE_VALIDATION.md`) is unaffected by construction: its estimands are
judge-vs-human, oracle-free.

## Method

Cross-referenced `reports/sample_manifest.json` (the pinned 100 instances) against both UTBoost
artifacts (repo `CUHK-Shenzhen-SE/UTBoost`, branch `main`, retrieved 2026-07-15):

1. `assets/useful_scripts/augTest.json` — the 36 instances with confirmed insufficient test
   coverage (weak suites can pass wrong patches → false `resolved`).
2. `update_SWE_Bench/updated_parser_test_instance_dict_verified.json` — 271 Verified instances
   whose `FAIL_TO_PASS`/`PASS_TO_PASS` annotations differ under UTBoost's refined log parser
   (diffed as sets against the original `princeton-nlp/SWE-bench_Verified` annotations, fetched
   from the HuggingFace datasets server; all 271 differ).

## Findings

**Insufficient-test overlap: 2/100** — `django__django-11133`, `django__django-12325`. Both are
judge-`not_declared` and oracle-`not_resolved` (unresolved / empty patch). Weak tests can only
inflate `resolved` — neither run was resolved, so neither can be a false pass. **No impact on any
cell that matters.**

**Changed-annotation overlap: 52/100**, of which **5 are among the judge's 19 `declared_success`**
(the primary-estimand denominator):

| Instance | 2×2 cell | Annotation change | Substantive? |
|---|---|---|---|
| django__django-11211 | B (declared/unresolved) | P2P ±1: docstring→test-id rename | No |
| django__django-12713 | A (declared/resolved) | P2P ±1: docstring→test-id rename | No |
| django__django-11477 | B | **F2P 3→2** (one required test dropped); P2P ±15/14 mostly renames | Yes |
| django__django-11848 | B | **F2P 2→1** (test moved F2P→P2P) | Yes |
| django__django-12308 | B | **F2P 2→1** (test moved F2P→P2P) | Yes |

The three substantive changes all *shrink* the `FAIL_TO_PASS` set (none empties it), i.e. they
**lower the bar for `resolved`**. The only possible direction of oracle error on the declared set
is therefore `unresolved → resolved` on up to 3 B-cell runs. No change adds a required test, so no
`resolved → unresolved` flip is possible among the 19.

## Sensitivity bound on the v1 primary estimand

Reported: `false_success_rate` = 10/19 = **0.53**, Wilson 95% CI [0.32, 0.73] → `NOT_SUPPORTED`
at the 0.50 threshold. Worst-case correction (all 3 substantive B-cell runs flip to resolved):
7/19 = **0.37**, CI [0.19, 0.59] → still `NOT_SUPPORTED`, by a wider margin.

**The pre-registered v1 verdict is invariant under every UTBoost-consistent oracle-error scenario:
the known errors can only push the false-success rate further below the threshold.** Whether the
three runs actually flip would require re-running the SWE-bench harness with UTBoost annotations
against Nemotron-Nano's patches — unnecessary, since no outcome changes the verdict.

## Disclosure line for the reports

> Known SWE-bench Verified label errors (UTBoost, ACL 2025) touch 5 of the 19 declared-success
> runs; the possible error direction only lowers the false-success rate (worst case 10/19 → 7/19),
> so the `NOT_SUPPORTED` verdict is robust to them. The judge-validation study is oracle-free and
> unaffected. Details: `reports/utboost-oracle-sensitivity.md`.

## Provenance

- UTBoost artifacts: `github.com/CUHK-Shenzhen-SE/UTBoost` @ `main`, retrieved 2026-07-15 (MIT).
- Original annotations: `princeton-nlp/SWE-bench_Verified` via `datasets-server.huggingface.co`,
  retrieved 2026-07-15 (500/500 instances).
- Comparison: set-equality on parsed `FAIL_TO_PASS`/`PASS_TO_PASS`; script preserved in the
  session scratchpad (`utboost_overlap.py`) — re-derivable from the two public sources and
  `reports/sample_manifest.json`.
