# ADR 0004 — CLI commands must not report success without an operation

Status: implemented; CI confirmation required before merge.

## Context

FR-CLI-001 acceptance probes found eight reserved command/action combinations
returning exit 0 and `status: ok` without performing any operation. `warrant
verify` without a path did the same. Invalid warrants returned exit 3 but the
human-readable output still said `ok`. Existing tests preserved one of these
incorrect success cases instead of testing an actual verification.

## Decision

- Reserved `frame`, `plan`, `execute`, `inspect`, `source add/test` and
  `warrant show/export` return exit 5 and `command_unavailable`. Help and README
  explicitly mark them unavailable. This change does not implement them.
- Verification requires a path. Missing, unreadable and malformed inputs return
  exit 2 with `warrant_required` or `warrant_unreadable`. No `valid` field is
  emitted when verification could not be performed.
- A checked warrant retains exit 0 / `valid: true` or exit 3 / `valid: false`.
  Human output distinguishes valid from INVALID rather than printing `ok`.
- JSON command errors go to stdout; human errors go to stderr. Parser usage
  errors retain argparse's existing behavior. The fallback is failure, so a
  future command cannot silently become successful without a handler.

## Compatibility and validation

No warrant schema or historical artifact changes. Automation relying on fake
success now receives a failure by design. FR-CLI-001 remains implemented until
CI confirms the candidate; its previous interface test is strengthened.
Subprocess tests exercise exit codes, both output formats, absent/malformed
inputs, no side effects for unavailable operations, and real generated/tampered
warrants. Coverage thresholds remain unchanged. Stable-product readiness still
requires the separate release criteria, including independent and agent studies.
