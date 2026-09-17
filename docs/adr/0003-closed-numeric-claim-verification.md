# ADR 0003 — Closed numerical claim verification

Status: implemented; full CI pending.

## Context

INV-001/002 were violated when claim-class linting admitted invented numeric
prose. Declared identification assumptions could also admit a causal sentence
without an actual causal estimator. A provenance edge alone does not validate
a sentence's contents.

## Decision

The runner verifies a closed canonical statement of computed descriptive group
means. Class linting and prerequisite gates are necessary but not sufficient.
VerdictEngine defaults to no verified candidates; the runner supplies only its
own computed summary. This is a trusted internal Python boundary, not an input
JSON verification flag. Causal, predictive and other prose is not certified.

Reject invalid outcomes/groups and multiple sources rather than endorsing an
aggregate with an implicit denominator change or ignored input. Include the
verifier revision in assessment identity. Preserve higher-priority integrity
and identification verdicts; the question verdict and candidate validity are
separate. Explain this explicitly in CLI, Markdown and warrant limitations.

## Compatibility

Question and public v1 schemas stay unchanged. Legacy text is still loadable
but no longer automatically supported. New observation keys are additive in an
existing open mapping. Six-decimal rounding is fixed, not caller configurable.
Existing warrants are unchanged and remain hash-verifiable; verification proves
integrity, not substantive correctness. Reassess old data to apply this fix.

Existing tests that permitted uncomputed causal estimates now assert refusal;
mean examples use independent expected values. Frozen benchmarks remain intact.
The external regression adds numeric falsification and swapped groups. Optional
true free text is still labelled valid and counted as false blocks, not relabelled
as invalid to improve a score. No quality gate or coverage threshold is lowered.

## Limits

This conservative verifier cannot validate arbitrary language, perform adjusted
causal estimation or establish population representativeness. Narrow-format
regression success is not stable-product validation. The extended evaluation
must accompany any claim about general natural-language performance.
