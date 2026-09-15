# ADR 0002 — Explicit identification assumptions and claim-scoped blockers

Status: implemented; CI review pending.

## Context

The assessment runner treated observed covariate overlap as exchangeability,
accepted overlap in just one stratum, and could allow claims despite integrity
blockers. Its graph attached unrelated findings to the positivity check. These
contradicted INV-001, INV-002, INV-008 and INV-010.

## Decision

- Empirical support requires exactly two non-null treatment levels in every
  declared target stratum, with non-null covariates. This conservative discrete
  check does not estimate population positivity. Continuous covariates need an
  explicitly reviewed upstream coarsening; automatic binning is not performed.
- `CausalContract.identification_assumptions` is an optional tuple of named
  assumptions. Existing contracts deserialize with an empty tuple. Free-form
  prose and overlap do not automatically acknowledge an identifying assumption.
- Missing identifying conditions are repairable missing evidence, not proof of
  fundamental non-identifiability. Empirical lack of support remains a design
  blocker. A declared assumption cannot override that blocker or a mismatch
  between the adjustment set and checked columns.
- Conditional identification produces `ANSWERABLE_WITH_ASSUMPTIONS`. No table
  check verifies random assignment, absence of unmeasured confounding, parallel
  trends, instrument validity or discontinuity validity merely because a user
  selected a strategy. The observed mean difference is still descriptive; this
  change does not implement adjusted causal estimation.
- Facts, declared assumptions and conditions not verifiable from the table are
  separate graph nodes and separate lists in
  `data_quality_relevance.evidence_status` in the warrant. Existing canonical
  top-level warrant sections remain unchanged. Markdown displays all three.
- Integrity/execution blockers affect all claims; other inference blockers
  prevent causal/predictive/diagnostic/recommendation claims regardless of
  wording. Raw descriptive associations may survive missing causal evidence.
  `causal_gate` is checked by claim class, not only an English verb regex.
- Each finding links to its actual producing check; observations link to the
  means computation. Plans/manifests and graph execution nodes use the same
  selected registry. Only the primary dataset is linked to these checks because
  this runner currently computes on the first dataset.
- Pure descriptive questions do not require causal identification or inferential
  power. Adding a causal candidate still activates causal checks.
- Assessment identity includes the complete mapping, causal contract and claim
  candidates. Changing acknowledged assumptions therefore changes identity.

## Compatibility and evidence

The v1 causal JSON schema accepts the new optional field; legacy payloads remain
valid. Graph schemas already accept string node types. Old warrant hashes are
not rewritten. Existing tests that equated overlap with unconditional support
now explicitly declare assumptions and assert the stricter conditional verdict.
No coverage or quality threshold is lowered.

EMT-v1/v2 frozen files and historical agent results remain untouched. The live
EMT fixture now declares conditional exchangeability explicitly. Its results are
not identical inputs to the historical frozen comparison, and the README states
this boundary. The existing EMT action scorer is mechanism-specific; it is not
used as the oracle for the new external claim evaluation.

## Limits

The claim linter is not a general semantic/numeric verifier of arbitrary prose.
The external evaluation validates a narrow set of exact observed-mean claims,
using independent standard-library arithmetic, and rejects unsupported causal
or duplicate-grain claims. Its questions/oracle are authored in this project.
Conditional identification does not certify a causal effect's sign or magnitude.

The paired agent experiment uses an actual mediated call to the same MCP handler,
not a simulated engine. It measures tool availability on fixed evidence summaries;
it is not a test of arbitrary autonomous exploration or native MCP transport.
