# Answerable SDD — Delivery Phases 10–12

## Scope

This document implements Sections 10.4–10.9 of the product specification. These modules emit typed
findings and bounded analytical results. They do not select the global Answerable verdict, which is
owned by Phase 13.

## Phase 10 — Statistical and experiment validity

`StatisticalAssessor` reports the estimate, standard error, confidence interval, standardized effect
size, p-value, corrected p-value, approximate design power, and minimum detectable effect. A
non-significant result never permits a “no effect” claim merely because its p-value exceeds alpha.
Bonferroni and Benjamini–Hochberg corrections are deterministic and bounded.

Assumption diagnostics expose influential observations, subgroup sign instability, and disagreement
between classical and robust alternatives.

`ExperimentAssessor` validates allocation against the declared randomization, exposure capture,
contamination, differential attrition, pre-experiment balance, declared sequential looks and stopping
rules, randomization/analysis-unit alignment, clustered uncertainty, and guardrail metrics.

## Phase 11 — Causal validity

`CausalContract` makes treatment, outcome, population, estimand, strategy, adjustment set,
assumptions, falsification checks, and sensitivity checks explicit. Supported strategy identifiers
cover randomized experiments, regression adjustment, matching/weighting, difference-in-differences,
interrupted time series, regression discontinuity, instrumental variables, synthetic control, and
panel estimators.

Identification is evaluated before estimation. When design evidence cannot identify the estimand,
the estimator is not called and causal language is explicitly forbidden. Refutation and sensitivity
remain separate from the point estimate.

## Phase 12 — Predictive, diagnostic, and prescriptive validity

Predictive assessment requires strictly separated train/validation/test periods, prediction-time
feature availability, baseline comparison, probability calibration, subgroup reliability, drift,
and mature labels. It fails closed on leakage, incomplete labels, or failure to beat the baseline.

Diagnostic assessment first verifies that metric movement is comparable. Additive contributions are
reconciled to the movement, unexplained residual is exposed, Simpson’s paradox is detected, and
contribution is never promoted to causality.

Prescriptive assessment requires an objective, at least two alternatives, constraints, uncertainty,
downside guardrails, and an explicit condition that would reverse the recommendation. Selection uses
conservative utility and excludes infeasible or guardrail-breaking alternatives.

## Verification

TDD covers underpowered nulls, multiple comparisons, robustness failures, SRM, sequential peeking,
randomization-unit mismatch, identification-before-estimation, all principal strategy gates,
temporal/feature leakage, calibration and baseline failures, Simpson’s paradox, causal overclaiming,
guardrails, uncertainty, and reversal conditions.
