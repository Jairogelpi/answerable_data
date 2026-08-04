# Answerable Thesis Specification

**Working title:** Answerable: Epistemic Mutation Testing for Data-Analysis Agents  
**Spanish title:** Pruebas de mutación epistémica para evaluar la fiabilidad de agentes de análisis de datos  
**Document status:** Normative draft  
**Version:** 0.1.0  
**Date:** 2026-08-04  
**Author:** Jairo Gelpi Moreno  
**Repository:** `Jairogelpi/answerable_data`

---

## 0. Purpose and authority

This document is the implementation and research contract for the master's thesis built in this repository.

The thesis is complete only when the research questions, benchmark, software, experiment, analysis, documentation, and reproducibility requirements defined here are satisfied. Product features that do not contribute directly to those requirements are out of scope.

When artifacts conflict, use this precedence:

1. this thesis specification;
2. versioned benchmark schemas and executable oracles;
3. automated acceptance tests;
4. the frozen experiment manifest;
5. methodology documentation;
6. README and explanatory prose.

The existing `docs/PRODUCT_SPEC.md` describes a broader analytical-validity product. This document narrows the thesis to a research contribution: evaluating data-analysis agents through semantics-aware dataset mutations and paired executable oracles.

---

## 1. Executive summary

Data-analysis agents are normally evaluated on whether they produce a correct answer for a fixed task. That evaluation can overestimate reliability. An agent may answer the original task correctly while failing to revise its conclusion after the evidence has been weakened, invalidated, or reversed.

Answerable will implement **epistemic mutation testing** for data-analysis agents.

The framework will:

1. generate a valid base analytical scenario;
2. apply a controlled mutation to its data, metadata, or analytical design;
3. execute the same agent on the original and mutated variants;
4. determine whether the conclusion should be maintained, qualified, retracted, or reversed;
5. compare the observed response against deterministic numerical and epistemic oracles;
6. calculate paired reliability metrics and expose surviving mutants.

The central thesis is:

> Static task accuracy is insufficient to characterize the reliability of data-analysis agents. Paired, semantics-aware mutations reveal whether an agent's conclusions track the evidence that is supposed to justify them.

Answerable is not a chat-with-data application and is not intended to answer arbitrary business questions. It is a benchmark, experiment runner, scoring framework, and reproducible research artifact.

---

## 2. Problem statement

A data-analysis agent can fail in at least two distinct ways:

1. **computational failure:** the reported number or result is wrong;
2. **epistemic failure:** the agent draws or preserves a conclusion that the available evidence does not justify.

Conventional task benchmarks primarily measure the first category. They usually evaluate one static dataset and one expected result. This does not reveal whether the model understands which properties of the evidence support its conclusion.

For example, an agent may correctly report that the treated group has twelve percentage points more retention than the control group. It may still incorrectly claim that the treatment caused the increase after a mutation introduces pre-existing confounding.

A reliable agent should react differently to different classes of change:

- preserve a conclusion after an irrelevant transformation;
- reduce confidence or add limitations when evidence weakens;
- retract a conclusion when a required assumption is invalidated;
- reverse a conclusion when the direction of the evidence reverses.

The research problem is to define, implement, and validate a systematic method for measuring those reactions.

---

## 3. Research objective

The primary objective is to determine whether paired epistemic mutation testing exposes reliability failures that are not visible in static evaluations of data-analysis agents.

The software objective is to release an open-source framework that makes this evaluation reproducible and extensible.

The project must produce:

- a formal mutation taxonomy;
- parametrized scenario generators;
- deterministic mutation operators;
- numerical and epistemic oracles;
- a common agent-output contract;
- paired scoring metrics;
- an experiment runner;
- an evaluated benchmark suite;
- a results dashboard or static report;
- a reproducible thesis analysis.

---

## 4. Research questions

### RQ1 — Static versus paired performance

Does static task accuracy overestimate the reliability of data-analysis agents compared with paired original-mutation accuracy?

### RQ2 — Invariance

Do agents preserve conclusions under transformations that leave the relevant statistical evidence unchanged?

### RQ3 — Qualification and retraction

Do agents correctly qualify or retract conclusions when evidence is weakened or invalidated?

### RQ4 — Reversal

Do agents reverse the direction of a conclusion when a controlled mutation reverses the underlying evidence?

### RQ5 — Failure families

Which mutation families produce the highest failure rates: metric integrity, temporal validity, experimental/causal validity, or predictive validity?

### RQ6 — Confidence

Is self-reported confidence calibrated to the validity and stability of the conclusion under mutation?

### RQ7 — Numerical correctness versus epistemic correctness

How often does an agent calculate the relevant statistic correctly but interpret it incorrectly?

---

## 5. Hypotheses

### H1

Static accuracy will be materially higher than paired accuracy.

### H2

Agents will perform better on `KEEP` mutations than on mutations requiring `QUALIFY`, `RETRACT`, or `REVERSE` behavior.

### H3

Experimental/causal and temporal mutations will produce more epistemic failures than purely structural mutations.

### H4

Self-reported confidence will be poorly calibrated to paired correctness.

### H5

A non-trivial proportion of failures will combine a numerically correct estimate with an unjustified interpretation.

### H6

General task-solving performance will not fully predict mutation sensitivity.

---

## 6. Research contribution

The intended contribution is not the invention of perturbation-based evaluation in general. Mutation testing, metamorphic testing, robustness testing, and paired benchmarks already exist.

The intended contribution is the integration of the following elements for data-analysis agents:

1. a multi-family taxonomy of semantics-aware analytical mutations;
2. paired original-mutant tasks generated from executable scenario specifications;
3. deterministic numerical oracles;
4. explicit epistemic transition labels: `KEEP`, `QUALIFY`, `RETRACT`, and `REVERSE`;
5. claim-level requirements and prohibitions;
6. paired metrics that distinguish invariance from invalidation sensitivity;
7. a reproducible runner and failure explorer.

The novelty claim must remain conservative:

> To the best of the documented literature review, no identified public benchmark combines a broad library of semantics-aware mutations for tabular data analysis, paired executable oracles, explicit conclusion-transition labels, and an end-to-end reusable evaluation framework.

This claim must be re-verified immediately before submission and must be weakened if new prior art is found.

---

## 7. Related work baseline

The literature review must include, at minimum, the following lines of work.

### 7.1 Data-science-agent benchmarks

- **DSBench** evaluates realistic data-analysis and data-modeling tasks and demonstrates that current agents struggle with end-to-end data science.
- **DiscoveryBench** evaluates multi-step data-driven hypothesis discovery using real and synthetic tasks.
- **AgenticDataBench** evaluates data agents across domains and fine-grained data-science skills.

These benchmarks primarily evaluate task completion or solution quality on static tasks.

### 7.2 Structured-data claim verification

- **ClaimDB** evaluates whether claims are entailed, contradicted, or unsupported by large structured databases and reports significant abstention difficulties.

ClaimDB is adjacent because it evaluates claims over data, but it does not define the thesis's broad paired mutation taxonomy or conclusion-transition framework.

### 7.3 Perturbation and stability checks

- **Sanity Checks for Agentic Data Science** uses perturbations grounded in the Predictability-Computability-Stability framework to expose conclusions that may be responding to noise or incidental details.

This is the closest identified prior work. The thesis must explicitly compare its scope with this work and must not claim that perturbation-based validity checking is new.

### 7.4 Paired abstention benchmarks

- **AgentAbstain** uses paired tasks where a small change determines whether an agent should act or abstain.

Answerable adopts the value of paired evaluation but applies it to the evidential semantics of data analysis rather than general tool-use action safety.

### 7.5 Required references

The bibliography must include at least:

- Jing et al. (2024), *DSBench: How Far Are Data Science Agents to Becoming Data Science Experts?*, arXiv:2409.07703.
- Majumder et al. (2024), *DiscoveryBench: Towards Data-Driven Discovery with Large Language Models*, arXiv:2407.01725.
- Rewolinski et al. (2026), *Sanity Checks for Agentic Data Science*, arXiv:2604.11003.
- Theologitis et al. (2026), *ClaimDB: A Fact Verification Benchmark over Large Structured Data*, ACL 2026 / arXiv:2601.14698.
- Liu et al. (2026), *AgentAbstain: Do LLM Agents Know When Not to Act?*, arXiv:2607.10059.
- Sun et al. (2026), *AgenticDataBench: A Comprehensive Benchmark for Data Agents*, arXiv:2607.01647.

A complete, traceable literature matrix must be maintained in `docs/RELATED_WORK.md` with columns for task, data type, static/paired design, perturbations, executable oracle, abstention, claim evaluation, and identified gap.

---

## 8. Scope

### 8.1 Included

- tabular datasets;
- synthetic data generated from versioned code;
- CSV and Parquet benchmark artifacts;
- four analytical families;
- paired original-mutant evaluation;
- controlled random seeds;
- Python-capable data-analysis agents;
- structured and free-text outputs;
- deterministic scoring where possible;
- manual validation of a stratified response sample;
- result tables, statistical analysis, and a failure gallery.

### 8.2 Excluded

- general-purpose chat with spreadsheets;
- arbitrary natural-language questions outside the scenario suite;
- production SaaS infrastructure;
- multi-tenancy and enterprise governance as thesis contributions;
- legal or regulatory certification;
- image, audio, or unstructured-document analysis;
- training a foundation model;
- comprehensive causal inference software;
- support for every forecasting or machine-learning task;
- real-time integrations with business systems;
- a large frontend application.

### 8.3 Thesis boundary

The minimum scientifically defensible thesis consists of:

- 12 base scenarios;
- 48 original-mutant pairs;
- all four expected response classes;
- four mutation families;
- three agent configurations;
- two repetitions per task variant;
- deterministic oracles with automated tests;
- a frozen benchmark manifest;
- paired statistical analysis;
- reproducible tables and figures.

Features beyond this boundary may be implemented only after the minimum experiment is operational.

---

## 9. Core terminology

### Scenario

A parametrized analytical task containing a question, data-generating process, metadata, base evidence, expected conclusion, and applicable mutation operators.

### Base instance

A concrete dataset and task generated from a scenario using a fixed seed before mutation.

### Mutation

A controlled transformation of data, metadata, analytical design, or evaluation context intended to preserve, weaken, invalidate, or reverse a conclusion.

### Mutant

The concrete mutated task produced by applying one mutation operator to one base instance.

### Numerical oracle

Executable code that calculates ground-truth properties of a base instance or mutant.

### Epistemic oracle

A specification of how a justified conclusion must change between the original and mutant.

### Mutant killed

The agent changes its response in the direction required by the epistemic oracle and satisfies mandatory claim and numerical constraints.

### Mutant survived

The agent fails to make the required change or violates a mandatory claim or numerical constraint.

### Paired correctness

Correct behavior on both the original instance and its associated mutant.

---

## 10. Epistemic transition classes

Every mutation must define exactly one primary expected transition.

### KEEP

The relevant evidence is unchanged. The conclusion should remain substantively equivalent.

Examples:

- row reordering;
- deterministic column renaming with supplied metadata;
- addition of an irrelevant column;
- equivalent date serialization;
- equivalent unit conversion with metadata.

A response fails `KEEP` if it changes the conclusion materially, abstains without justification, or produces inconsistent numerical results beyond tolerance.

### QUALIFY

The direction or central result may remain, but uncertainty or limitations increase materially.

Examples:

- reduced sample size;
- moderate missingness;
- weaker overlap;
- reduced temporal coverage;
- subgroup instability without full invalidation.

A response fails `QUALIFY` if it presents the original conclusion without the required limitation or retracts it unnecessarily.

### RETRACT

A required assumption or evidential basis has been invalidated. The original conclusion must be withdrawn or replaced by a narrower non-committal claim.

Examples:

- target leakage;
- incomplete outcome windows;
- invalid comparison group;
- join-induced metric inflation;
- model not beating a declared baseline;
- severe differential attrition.

### REVERSE

The evidence now supports the opposite direction or class.

Examples:

- positive treatment effect changed to negative;
- control group changed to outperform treatment;
- model ranking changed below baseline;
- metric direction changed after correcting duplicated entities.

A response fails `REVERSE` if it retains, merely qualifies, or retracts the old direction when the opposite conclusion is justified.

---

## 11. Mutation taxonomy

The benchmark must contain all four families. Each operator must declare its preconditions, transformation, preserved invariants, changed properties, expected transition, and oracle.

### 11.1 Metric integrity and relational structure

Required candidate operators:

- `row_reordering` — preserve evidence, `KEEP`;
- `duplicate_entities` — create duplicate business entities;
- `join_fanout` — multiply a measure through an invalid join;
- `grain_shift` — change the unit represented by a row;
- `drop_credit_notes` — remove negative adjustments;
- `mixed_currency` — combine monetary values without conversion;
- `truncate_period` — remove the end of a reporting period;
- `denominator_shift` — change population denominator;
- `filter_asymmetry` — apply inconsistent filters across compared groups.

Mandatory base scenarios must include at least:

- revenue or transaction totals;
- conversion or rate metrics;
- customer/entity counts.

### 11.2 Temporal validity and cohorts

Required candidate operators:

- `immature_cohort` — move entity start dates so the observation window is incomplete;
- `right_censoring` — hide or delay outcomes after the analysis cutoff;
- `future_feature` — make a predictor unavailable at prediction time;
- `unequal_windows` — assign different observation windows across groups;
- `temporal_gap` — remove a meaningful time interval;
- `definition_change` — change metric semantics during the period;
- `delayed_label` — make evaluation labels incomplete;
- `cutoff_shift` — change the analytical cutoff date.

Mandatory base scenarios must include at least:

- retention or churn;
- time-bounded outcome evaluation;
- temporal model validation.

### 11.3 Experimental and causal validity

Required candidate operators:

- `break_randomization` — correlate assignment with a pre-treatment feature;
- `sample_ratio_mismatch` — alter assignment proportions unexpectedly;
- `treatment_contamination` — expose control units to treatment;
- `differential_attrition` — remove outcomes unequally by arm;
- `reduce_power` — decrease sample size or effect precision;
- `inject_confounding` — create a common cause of treatment and outcome;
- `simpsons_paradox` — reverse aggregate and subgroup associations;
- `destroy_effect` — permute treatment or outcome to remove the signal;
- `reverse_effect` — change the true effect direction.

The thesis must distinguish descriptive group differences from identified causal effects. It must not claim to solve general causal identification.

### 11.4 Predictive validity

Required candidate operators:

- `target_leakage` — expose target-derived information to the model;
- `train_test_overlap` — duplicate entities across evaluation splits;
- `invalid_temporal_split` — train using observations later than test predictions;
- `stronger_baseline` — introduce or reveal a baseline superior to the model;
- `destroy_calibration` — preserve ranking while distorting probabilities;
- `prevalence_shift` — change class prevalence;
- `covariate_drift` — shift input distributions;
- `subgroup_degradation` — reduce performance for one group;
- `immature_labels` — make some outcomes unknown at evaluation time;
- `reverse_ranking` — alter predictions so discrimination reverses.

Mandatory base scenarios must include at least:

- binary classification;
- calibrated probability assessment;
- subgroup evaluation.

---

## 12. Scenario specification

Each scenario must be represented by a versioned YAML document validated against a JSON Schema.

Minimum logical structure:

```yaml
schema_version: "1.0"
scenario_id: campaign_retention_01
family: experimental_causal
title: Campaign effect on 90-day retention

question:
  text: Did the campaign increase 90-day retention?
  claim_type: causal

base:
  generator: campaign_retention
  seed: 42
  parameters:
    sample_size: 2000
    treatment_probability: 0.5
    effect_size: 0.08
    observation_window_days: 90

oracle:
  expected_status: supported
  expected_direction: positive
  numeric_tolerances:
    effect_size_absolute: 0.01
  required_findings:
    - mature_outcomes
    - valid_comparison
  forbidden_claims: []

mutations:
  - mutation_id: rows_reordered
    operator: metric_integrity.row_reordering
    expected_transition: KEEP

  - mutation_id: cohort_immaturity
    operator: temporal.immature_cohort
    parameters:
      immature_fraction: 0.40
    expected_transition: RETRACT
    required_findings:
      - incomplete_outcome_window
```

A scenario must not enter the frozen benchmark until:

- its schema validates;
- its generator is deterministic for a fixed seed;
- its numerical oracle passes independent tests;
- every mutation precondition is verified;
- the expected transition is reviewed;
- the generated data contain no accidental shortcut that trivializes the task.

---

## 13. Agent input protocol

Every evaluated agent must receive equivalent information and capabilities within an experiment condition.

Minimum task bundle:

- question in natural language;
- dataset files;
- data dictionary and relevant metadata;
- requested structured response schema;
- permission to execute Python in an isolated workspace;
- explicit instruction to inspect data rather than infer results from filenames.

The task bundle must not reveal:

- mutation identity;
- expected transition;
- oracle outputs;
- required findings;
- whether the task is an original or mutant.

Prompts must be versioned and hashed. Any model-specific adaptation must be documented and must preserve task semantics.

---

## 14. Agent output contract

Agents must produce free text and a machine-readable result.

Required logical fields:

```json
{
  "conclusion_status": "supported_with_caveats",
  "effect_direction": "positive",
  "answer": "The exposed group has higher observed retention, but...",
  "numeric_results": {
    "effect_size": 0.12
  },
  "findings": [
    "groups_not_comparable"
  ],
  "allowed_claims": [
    "Observed retention was higher in the exposed group."
  ],
  "forbidden_claims": [
    "The campaign caused the increase."
  ],
  "confidence": 0.61
}
```

Allowed `conclusion_status` values:

- `supported`;
- `supported_with_caveats`;
- `not_supported`;
- `reversed`;
- `insufficient_information`;
- `unsupported_task`;
- `execution_failure`.

Allowed `effect_direction` values:

- `positive`;
- `negative`;
- `neutral`;
- `mixed`;
- `unknown`;
- `not_applicable`.

Parsing failure must be recorded as a failure mode. A single bounded repair attempt may be used to convert otherwise complete output into valid JSON. The raw response must never be discarded or overwritten.

---

## 15. Oracles

### 15.1 Numerical oracle

Each scenario must expose executable functions that calculate the relevant ground truth directly from generated data.

Depending on the scenario, these may include:

- correct metric value;
- row and entity counts;
- join fanout;
- effect direction and size;
- confidence interval;
- cohort maturity fraction;
- censoring fraction;
- leakage presence;
- baseline performance;
- Brier score, log loss, ROC-AUC, PR-AUC, and calibration values;
- subgroup metrics;
- expected assignment proportions.

Oracle computations must use established statistical implementations where appropriate. Hand-written approximations must be justified and tested against trusted reference implementations.

### 15.2 Epistemic oracle

The epistemic oracle defines:

- expected transition: `KEEP`, `QUALIFY`, `RETRACT`, or `REVERSE`;
- acceptable conclusion status;
- expected direction;
- mandatory findings;
- forbidden findings;
- required allowed-claim semantics;
- prohibited claim semantics;
- numerical tolerances;
- whether abstention is required, permitted, or incorrect.

### 15.3 Claim oracle

Claim scoring should prefer structured semantic labels over exact-string matching.

The first release may use:

- deterministic phrase and label rules for clearly defined claims;
- structured finding identifiers;
- numerical consistency checks;
- manually reviewed rules for scenario-specific claims.

An LLM judge must not be the sole source of ground truth. If an LLM-assisted semantic judge is used, its agreement with human annotations must be measured and its outputs treated as secondary evidence.

---

## 16. Scoring

### 16.1 Static accuracy

The proportion of original tasks whose structured response satisfies the base oracle.

### 16.2 Paired accuracy

The proportion of original-mutant pairs for which the agent satisfies both the original oracle and the mutation transition oracle.

### 16.3 Invariance accuracy

Accuracy restricted to `KEEP` mutations.

### 16.4 Qualification accuracy

Accuracy restricted to `QUALIFY` mutations.

### 16.5 Invalidation sensitivity

Accuracy restricted to `RETRACT` mutations.

### 16.6 Reversal accuracy

Accuracy restricted to `REVERSE` mutations.

### 16.7 Mutation kill rate

The proportion of mutants for which the agent makes the required epistemic transition and satisfies mandatory claim constraints.

A mutant is killed only when the transition is correct. Any arbitrary response change is insufficient.

### 16.8 Causal overreach rate

The proportion of tasks without identified causal evidence in which the response makes an unqualified causal claim.

### 16.9 Abstention metrics

Report:

- abstention precision;
- abstention recall;
- unnecessary abstention rate;
- failure-to-abstain rate.

### 16.10 Numerical consistency

The proportion of reported numerical results within scenario-specific oracle tolerances.

### 16.11 Epistemic Mutation Score

The primary aggregate score is the unweighted macro-average of:

- invariance accuracy;
- qualification accuracy;
- invalidation sensitivity;
- reversal accuracy.

The aggregate must never be published without its four components. Missing transition classes make the aggregate undefined rather than silently assigning zero or excluding the class.

### 16.12 Confidence calibration

Where agents provide confidence, report:

- Brier score for paired correctness;
- expected calibration error;
- reliability plot;
- mean confidence for correct and incorrect responses.

---

## 17. Benchmark composition

### 17.1 Minimum benchmark

- 12 base scenario templates;
- 3 base scenarios per family;
- 4 mutations per base scenario;
- 48 distinct original-mutant pairs;
- at least one operator of every expected transition class in every feasible family;
- 2 generation seeds;
- 3 agent configurations;
- 2 repeated executions per task variant.

Approximate minimum number of agent executions:

```text
48 pairs × 2 task variants × 2 seeds × 3 agents × 2 repetitions = 1,152
```

### 17.2 Target benchmark

- 16 base scenarios;
- 4 base scenarios per family;
- 64 original-mutant pairs;
- 3 generation seeds;
- 3 agent configurations;
- 2 repetitions.

Approximate target number of executions:

```text
64 pairs × 2 task variants × 3 seeds × 3 agents × 2 repetitions = 2,304
```

### 17.3 Composition constraints

The benchmark must avoid being dominated by one family, transition, or trivial operator.

The frozen manifest must report counts by:

- family;
- scenario;
- mutation operator;
- transition class;
- seed;
- expected conclusion status;
- expected effect direction.

---

## 18. Evaluated systems

The final experiment must evaluate at least three distinct agent configurations.

Recommended design:

1. a high-capability closed model with Python/tool use;
2. a different closed or open model in the medium-cost tier;
3. an open-weight or local model when hardware permits, otherwise a third materially different hosted model.

The study evaluates configurations rather than brands. For every run, record:

- provider;
- exact model identifier and snapshot where available;
- execution date;
- agent harness version;
- system and task prompt hashes;
- temperature and sampling parameters;
- tool permissions;
- token limits;
- retry policy;
- execution duration;
- token usage and estimated cost;
- raw answer;
- structured answer;
- generated code;
- stdout, stderr, and produced artifacts.

Model changes during the experiment are prohibited unless the entire affected condition is rerun or the change is reported as a separate condition.

---

## 19. Baselines

### 19.1 Static-only evaluation

Evaluate agents only on base instances. This demonstrates what a conventional benchmark would report.

### 19.2 Insensitive baseline

Return the original conclusion for every mutant. This establishes the behavior of a system that is entirely insensitive to evidential changes.

### 19.3 Conservative baseline

Abstain on every task. This establishes the opposite failure mode.

### 19.4 Deterministic oracle baseline

Use scenario-specific numerical oracles without language generation. This is not a general agent but establishes the maximum achievable score on supported structured checks.

### 19.5 Optional prompt baseline

Compare a standard analysis prompt against an explicit verification-oriented prompt while keeping the underlying model constant. This condition is optional and must not replace the multi-agent comparison.

---

## 20. Experimental protocol

### 20.1 Development split

Scenario templates used during implementation and prompt debugging must be marked as development scenarios.

### 20.2 Frozen evaluation split

Before final model execution:

- freeze the scenario and mutation code commit;
- freeze the benchmark manifest;
- freeze prompts and agent configurations;
- calculate and record file hashes;
- run all oracle tests;
- tag the repository state.

No benchmark modification is permitted after observing final results except to correct a demonstrated defect. Corrections must be documented, the affected experiment rerun, and both versions preserved.

### 20.3 Randomization

Execution order must be randomized within each agent condition. Original and mutant variants must not be presented consecutively by default.

### 20.4 Independence and clustering

Mutants derived from the same base scenario are not statistically independent. Analysis must cluster or resample at the base-scenario level where appropriate.

### 20.5 Failure handling

Execution failures, timeouts, parsing failures, and tool failures must be retained as outcomes. Retries must follow a fixed pre-registered policy.

### 20.6 Cost control

A pilot run must estimate cost before the final experiment. The final manifest must define maximum tokens, timeouts, and retry counts. Reducing the number of repetitions is preferable to silently changing task content when cost exceeds the budget.

---

## 21. Statistical analysis

The final analysis must include more than point estimates.

Required methods:

- cluster bootstrap confidence intervals by base scenario;
- paired comparisons between static and mutation-aware outcomes;
- McNemar tests for paired binary outcomes when assumptions are satisfied;
- permutation tests for aggregate score differences;
- effect sizes with confidence intervals;
- Holm correction for families of multiple comparisons;
- analysis by family, operator, transition class, and agent;
- sensitivity analysis over seeds and repetitions.

The unit of inference must be explicit. Individual repeated executions must not be treated as independent benchmark scenarios.

Results must distinguish exploratory from confirmatory analyses.

---

## 22. Human validation

Automatic scoring must be validated against human judgment.

Minimum protocol:

- sample 15–20% of responses using stratification by family, transition, agent, and automatic outcome;
- hide agent identity and oracle labels from annotators;
- independently annotate conclusion status, direction, required qualification, causal overreach, and overall correctness;
- use two annotators when feasible;
- calculate Cohen's kappa or an appropriate agreement statistic;
- adjudicate disagreements and preserve both original annotations;
- report the agreement between automatic and adjudicated scoring.

If only one independent annotator is available, this limitation must be stated and a smaller second-review sample should be obtained from the thesis supervisor or another qualified reviewer where possible.

---

## 23. Software architecture

The target architecture is research-first and must avoid unnecessary enterprise scope.

```text
src/answerable/
├── scenarios/
│   ├── models.py
│   ├── registry.py
│   ├── loader.py
│   └── generators/
├── mutations/
│   ├── base.py
│   ├── metric_integrity/
│   ├── temporal/
│   ├── experimental_causal/
│   └── predictive/
├── oracles/
│   ├── numeric.py
│   ├── epistemic.py
│   └── claims.py
├── agents/
│   ├── base.py
│   ├── structured.py
│   ├── scripted.py
│   └── providers/
├── runner/
│   ├── execution.py
│   ├── workspace.py
│   ├── retry.py
│   └── artifacts.py
├── scoring/
│   ├── static.py
│   ├── paired.py
│   ├── claims.py
│   ├── confidence.py
│   └── statistics.py
├── reporting/
│   ├── tables.py
│   ├── figures.py
│   └── html.py
└── cli.py

benchmark/
├── schemas/
├── scenarios/
├── manifests/
└── generated/

experiments/
├── configs/
├── raw/
├── processed/
└── results/

paper/
├── manuscript/
├── tables/
└── figures/
```

Existing Answerable components may be reused when they reduce implementation risk and preserve methodological clarity:

- deterministic findings;
- verdict precedence;
- allowed and forbidden claims;
- evidence graphs;
- content hashing;
- immutable warrants;
- guarded execution;
- schema validation;
- strict typing and CI.

Enterprise connectors, multi-tenancy, backup, hosted-product infrastructure, and generic web screens are not thesis priorities.

---

## 24. Command-line interface

Required commands:

```bash
answerable scenario list
answerable scenario validate benchmark/scenarios/campaign_retention.yaml
answerable scenario generate campaign_retention_01 --seed 42 --output benchmark/generated/
answerable mutate campaign_retention_01 --operator temporal.immature_cohort
answerable oracle campaign_retention_01 --seed 42
answerable run --manifest benchmark/manifests/core-v1.yaml --agents experiments/configs/agents.yaml
answerable score experiments/raw/run-001
answerable compare experiments/results/run-001 experiments/results/run-002
answerable report experiments/results/core-v1 --format html
answerable reproduce paper
```

All commands must support machine-readable JSON output and meaningful non-zero exit codes.

---

## 25. Artifact and provenance requirements

Every generated base instance, mutant, and agent execution must be content-addressed or accompanied by a cryptographic hash.

A run manifest must include:

- repository commit;
- benchmark version;
- scenario specification hash;
- generator and mutation versions;
- seed;
- dataset hashes;
- prompt hashes;
- agent configuration;
- environment information;
- timestamps;
- raw and parsed outputs;
- scorer version;
- oracle results;
- final score record.

Raw agent responses and generated code are immutable experiment artifacts. Corrections create derived artifacts and never replace the original.

No secret or API credential may be written into experiment artifacts.

---

## 26. Reproducibility

The repository must provide:

- locked dependencies;
- deterministic data generators;
- fixed random seeds;
- Dockerfile or equivalent environment definition;
- Makefile or task runner;
- versioned prompts and schemas;
- scripts that regenerate benchmark data;
- scripts that rescore stored model outputs;
- scripts that reproduce thesis tables and figures;
- stored final raw outputs when licensing and privacy permit.

Required top-level command:

```bash
make reproduce
```

This command must reproduce all thesis tables and figures from frozen stored outputs without calling external model APIs.

A separate command may rerun the models when credentials are supplied, but it is not required for ordinary paper reproduction.

---

## 27. Testing and quality gates

Required automated checks:

- formatting and linting;
- strict static typing;
- unit tests;
- schema tests;
- scenario determinism tests;
- mutation precondition and postcondition tests;
- oracle reference tests;
- scoring tests;
- artifact hash tests;
- CLI contract tests;
- one complete end-to-end golden-case test;
- benchmark smoke test;
- package build and clean installation;
- documentation link and example checks.

Every mutation operator must have tests proving:

1. deterministic behavior for a fixed seed;
2. expected property change;
3. preservation of declared invariants;
4. compatibility with its numerical oracle;
5. rejection when preconditions are not met.

Coverage percentage is secondary to semantic coverage. A high coverage score does not substitute for independent oracle validation.

---

## 28. Golden scenario

The first complete scenario must be **campaign effect on 90-day retention**.

### Base instance

- two groups;
- valid randomized assignment;
- mature outcomes;
- positive treatment effect;
- sufficient sample size;
- no contamination;
- stable metric definition.

### Required mutations

1. `row_reordering` → `KEEP`;
2. `reduce_power` → `QUALIFY`;
3. `immature_cohort` → `RETRACT`;
4. `inject_confounding` → `RETRACT` for the causal claim while permitting a descriptive difference;
5. `reverse_effect` → `REVERSE`.

### Golden acceptance path

```text
scenario specification
→ deterministic base generation
→ numerical oracle
→ mutation generation
→ mutation oracle
→ simulated agent outputs
→ paired scoring
→ HTML or Markdown report
```

No additional family should be implemented until this path works end to end without an external LLM.

---

## 29. Dashboard and reporting

The visual artifact is a research-results interface, not a chat application.

Required views:

### Leaderboard

- static accuracy;
- paired accuracy;
- Epistemic Mutation Score;
- component transition accuracies;
- causal overreach;
- abstention metrics;
- numerical consistency.

### Family analysis

Results grouped by:

- metric integrity;
- temporal validity;
- experimental/causal validity;
- predictive validity.

### Mutation analysis

Per-operator kill rates and confidence intervals.

### Pair explorer

For each pair:

- base question and data summary;
- mutation description hidden during evaluation but visible in analysis;
- original response;
- mutant response;
- expected transition;
- observed transition;
- required and missing findings;
- numerical oracle comparison;
- killed or survived status.

### Failure gallery

A curated set of high-value surviving mutants, including cases where the number is correct but the conclusion is invalid.

The dashboard may be implemented as a static HTML report, Streamlit application, or lightweight web application. It must not delay the experiment.

---

## 30. Thesis manuscript structure

### Chapter 1 — Introduction

- context and motivation;
- limitations of static data-agent evaluation;
- epistemic failure problem;
- objectives, questions, and contributions.

### Chapter 2 — Related work

- data-science agents;
- data-analysis benchmarks;
- claim verification over structured data;
- mutation and metamorphic testing;
- robustness and stability;
- abstention;
- perturbation-based data-science evaluation.

### Chapter 3 — Conceptual framework

- analytical conclusion;
- evidence and assumptions;
- mutation semantics;
- `KEEP`, `QUALIFY`, `RETRACT`, `REVERSE`;
- killed and surviving mutants;
- formal scoring definitions.

### Chapter 4 — Benchmark methodology

- scenario selection;
- generators;
- taxonomy;
- oracles;
- agent protocol;
- scoring;
- human validation.

### Chapter 5 — Implementation

- architecture;
- schemas;
- CLI;
- runner;
- artifact persistence;
- reproducibility and testing.

### Chapter 6 — Experimental design

- evaluated systems;
- prompts and tools;
- frozen manifest;
- repetitions and seeds;
- statistical analysis plan.

### Chapter 7 — Results

- static and paired results;
- family and operator analysis;
- confidence calibration;
- numerical versus epistemic correctness;
- statistical comparisons.

### Chapter 8 — Error analysis

- surviving mutants;
- causal overreach;
- temporal failures;
- calibration failures;
- superficial instability;
- parsing and tool failures.

### Chapter 9 — Discussion

- answers to research questions;
- implications for benchmark design;
- implications for data-agent deployment;
- comparison with prior work.

### Chapter 10 — Limitations, ethics, and threats to validity

- synthetic scenarios;
- benchmark coverage;
- model drift;
- prompt sensitivity;
- oracle validity;
- external validity;
- cost and reproducibility;
- benchmark contamination.

### Chapter 11 — Conclusions and future work

- findings;
- released contributions;
- extensions to real datasets, additional analysis families, and continuously generated hidden evaluations.

---

## 31. Threats to validity

The thesis must discuss at least:

### Construct validity

- whether transition labels capture the intended notion of epistemic reliability;
- whether structured outputs distort natural agent behavior;
- whether claim rules adequately represent nuanced conclusions.

### Internal validity

- prompt differences;
- non-deterministic model behavior;
- parsing and execution failures;
- accidental shortcuts in synthetic data;
- oracle implementation defects.

### External validity

- synthetic versus real-world datasets;
- limited analytical families;
- limited agent and harness coverage;
- generalization beyond tabular data;
- generalization to organization-specific semantics.

### Statistical conclusion validity

- clustered tasks;
- multiple comparisons;
- limited scenario count;
- repeated runs from the same model;
- uncertainty in human labels.

### Temporal validity

- hosted models may change after evaluation;
- provider snapshots may be unavailable;
- results represent specific configurations and dates.

---

## 32. Ethics and responsible publication

The benchmark must not include personal or sensitive production data.

Synthetic datasets should avoid reinforcing harmful stereotypes. Protected-group scenarios may be included only when necessary to test subgroup reliability and must use neutral synthetic labels or clearly documented simulated attributes.

The thesis must not present Answerable as certifying truth, regulatory compliance, or safety. It evaluates behavior on a bounded benchmark.

Model rankings must include uncertainty and methodological context. Small score differences must not be presented as meaningful without statistical support.

Raw model outputs may contain unsafe or inappropriate content and should be handled as research artifacts with appropriate warnings.

---

## 33. Documentation deliverables

Required repository documents:

- `docs/THESIS_SPEC.md`;
- `docs/RELATED_WORK.md`;
- `docs/MUTATION_TAXONOMY.md`;
- `docs/METHODOLOGY.md`;
- `docs/BENCHMARK_CARD.md`;
- `docs/DATA_CARD.md`;
- `docs/AGENT_PROTOCOL.md`;
- `docs/REPRODUCIBILITY.md`;
- `docs/LIMITATIONS.md`;
- `docs/ETHICS.md`;
- `CITATION.cff`;
- final README;
- changelog and release notes.

The benchmark and generated synthetic data should use a clear data license, preferably CC BY 4.0 unless another license is better justified. Source code remains under the repository software license.

---

## 34. Five-week delivery plan

### Week 1 — Scientific definition and golden path

Deliver:

- final thesis scope;
- initial related-work matrix;
- mutation taxonomy draft;
- scenario and output schemas;
- golden campaign-retention generator;
- five golden mutations;
- numerical and epistemic oracles;
- simulated-agent paired scoring;
- first end-to-end report.

Exit gate:

- the golden scenario completes the entire pipeline without an external model.

### Week 2 — Benchmark implementation

Deliver:

- all four mutation families;
- minimum 12 base scenarios;
- minimum 48 pairs;
- two seeds;
- complete oracle tests;
- benchmark smoke suite;
- benchmark card draft.

Exit gate:

- every frozen-candidate scenario validates and its oracle tests pass.

### Week 3 — Agent runner and pilot

Deliver:

- common agent adapter;
- three agent configurations;
- artifact persistence;
- retry and timeout handling;
- raw and structured output capture;
- static, insensitive, conservative, and oracle baselines;
- pilot of at least 100 executions;
- cost and failure-rate estimate.

Exit gate:

- parsing, execution, and scoring failure rates are understood and acceptable.

### Week 4 — Frozen experiment and analysis

Deliver:

- frozen benchmark manifest and repository tag;
- complete agent executions;
- processed result dataset;
- human-validation sample;
- statistical analysis;
- tables, figures, and failure gallery;
- dashboard or HTML report.

Exit gate:

- all research questions have corresponding evidence or are explicitly reported as unanswered.

### Week 5 — Manuscript, defense, and release

Deliver:

- final thesis manuscript;
- reproducibility documentation;
- final README;
- release `v1.0.0` or thesis-specific release;
- presentation;
- three-minute demonstration;
- archived benchmark and results;
- DOI through Zenodo or an equivalent repository when feasible.

Exit gate:

- a clean checkout can reproduce the reported tables and figures from stored outputs.

---

## 35. Definition of done

The thesis is complete only when all of the following are true:

### Scientific

- research questions and hypotheses are frozen;
- related work is current through the submission date;
- the novelty claim is conservative and supported;
- benchmark composition satisfies the minimum scope;
- all four mutation families and transition classes are represented;
- at least three agent configurations are evaluated;
- static and paired evaluations are compared;
- uncertainty and paired statistical analyses are reported;
- human validation of automatic scoring is completed;
- threats to validity and negative results are documented.

### Technical

- all scenario and output schemas validate;
- generators are deterministic under fixed seeds;
- all mutation operators have semantic tests;
- all numerical oracles have independent reference tests;
- the golden scenario passes end to end;
- raw outputs and provenance are preserved;
- the experiment can be rescored without external APIs;
- `make reproduce` regenerates thesis tables and figures;
- CI is green from a clean checkout;
- package installation and CLI work as documented.

### Publication

- README explains the research problem in one screen;
- benchmark card and data card are published;
- methodology is sufficiently detailed for replication;
- a stable release is tagged;
- citation metadata are available;
- the defense includes a live or recorded mutant-survival demonstration.

---

## 36. Immediate implementation order

The next implementation work must follow this order:

1. create scenario and agent-output JSON Schemas;
2. implement the campaign-retention generator;
3. implement and test its numerical oracle;
4. implement `KEEP`, `QUALIFY`, `RETRACT`, and `REVERSE` golden mutations;
5. implement the epistemic oracle model;
6. implement simulated-agent outputs;
7. implement paired scoring;
8. produce the first report;
9. review the golden case for conceptual clarity;
10. only then add further scenarios and real agent adapters.

No frontend, enterprise connector, MCP extension, or generic question compiler should be implemented before item 8 passes.

---

## 37. Final product definition

> Answerable is an epistemic mutation-testing framework for data-analysis agents. It measures whether their conclusions remain stable when they should and are qualified, retracted, or reversed when the supporting evidence changes.

This definition must remain the organizing principle of the thesis, repository, experiment, README, and defense.
