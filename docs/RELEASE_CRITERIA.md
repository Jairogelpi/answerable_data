# Stable release criteria

Current decision: **NOT READY for a stable release**. Alpha/pilot use is possible
within the documented scope. Passing software CI alone cannot change this decision.
These are prospective acceptance criteria, not claims of completed validation.
Freeze their version with the evaluation manifest before exposing held-out results.

## Scope of the proposed stable package

The release promises checks of explicit data and analysis conditions, deterministic
blockers and traceable reports through Python, CLI and MCP. It does not promise
universal conclusion verification, automatic causal proof, adjusted causal effect
estimation or a finished hosted application. PRODUCT_SPEC.md remains the target
implementation contract; these gates do not waive its applicable invariants.

## Gates

| Gate | Acceptance criterion | Current state | Evidence owner |
| --- | --- | --- | --- |
| Scope and documentation | Each advertised capability maps to an executable example/test and a stated boundary | Documentation supplied; candidate review required | Maintainer |
| Software quality | Full CI passes with >=95% branch-aware coverage, strict types, lint, schemas and traceability; no weakened thresholds | Previous Linux baseline passed; candidate CI required | CI + maintainer |
| Distribution | Clean wheel installs on Linux 3.11/3.12 and Windows 3.12; public/CLI/distribution versions agree; CLI and MCP work outside checkout | Candidate matrix/checks added; CI required | CI |
| Critical regression safety | Zero failures in the predefined critical suite: integrity blockers, unsupported causal claims, provenance and warrant tampering | Existing regressions passed; candidate CI required | CI + reviewer |
| Independent evaluation | At least 100 reviewed questions across 10 external datasets; at least five whole datasets reserved, containing >=40 valid and >=40 invalid questions in total | Pending | Independent domain reviewer |
| Held-out safety | Zero allowed critical-invalid claims; <=5% unsafe allows among all invalid claims; <=5% false blocks among valid claims, at both claim-list and primary-gate levels | Pending | Evaluation owner |
| Scope recognition and reliability | All predefined unsupported/ambiguous cases return an explicit limitation or block; zero execution errors in the fixed acceptance run | Pending | Evaluation owner |
| Agent integration benefit | Positive reduction in unsafe allows with a 95% dataset-cluster interval excluding zero; false-block increase <=2 percentage points; complete intended comparison matrix | Not run | Evaluation owner + authenticated model access |
| User pilots | At least three external users over two weeks; each completes a predefined task from published instructions without maintainer intervention; failures documented | Pending | Pilot users + maintainer |
| Release review | No open critical security, data-loss, disclosure or verdict/claim inconsistency issue; migration notes, candidate artifact digest and rollback instructions recorded | Pending | Maintainer |

These thresholds are engineering acceptance choices, not guarantees about all data.
Publish counts, denominators and uncertainty even when all observed cases pass.
Zero observed failures is not a zero population error rate. More datasets may be
needed for meaningful uncertainty estimates; five held-out clusters is a floor,
not a justification to claim a precise efficacy result.

## Evaluation rules

Follow the [external protocol](../benchmarks/external/README.md). Keep development
and reserved datasets disjoint, preserve disputed/ambiguous labels, and freeze
questions, claims, labels, hashes and thresholds before the candidate run.
Errors and missing responses are never dropped or relabelled as safe blocks.
Report per-dataset and per-claim-class results as well as pooled counts.

For agent comparison, hold model version, evidence, prompts, budget and repetition
policy fixed except for tool availability. Report tool usage, complete pairs,
improvements/regressions, latency and actual provider usage/cost when available.
Resample whole datasets for uncertainty; repeated calls and mutations are not
independent observations. The acceptance gate requires the complete planned run;
incomplete runs may be published as incomplete but cannot satisfy the gate.
If the agent already makes no unsafe decisions, safety improvement is inconclusive,
not a successful superiority claim. Broaden the prospectively defined evaluation.

## Candidate and release record

1. Maintainer nominates a commit and builds a release candidate with an explicit
   version. Record its wheel digest, dependencies, OS/Python matrix and CI URLs.
2. Evaluation owner freezes manifests and runs all gates on that candidate.
3. Independent reviewer checks labels, disagreements, limitations and results.
4. Maintainer records each gate as pass, fail or pending with a supporting URL.
   Missing evidence means pending, never pass.
5. After all gates pass, publish versioned release notes and installation examples.
   Archive the previous known-good artifact and explain how to reinstall its version.

If a fix follows held-out failure, retain the failed result. The exposed cases become
regressions; obtain a fresh reserved set before making a new generalization claim.
Never lower a threshold after observing results to make the candidate pass.
No release tag or PyPI publication is performed merely by adding this document.
