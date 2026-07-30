# Operations runbook

## Health and incident response

Check API health/readiness, dependency status, queue depth, failure rate, latency, retries and
resource usage. Correlate by request, assessment and execution IDs; telemetry must contain no rows or
secrets. Stop scheduling before isolating a failing executor or connector.

## Backup and recovery

Target RPO is 15 minutes and RTO is four hours. Restore into an isolated environment, validate
tenant counts, artifact hashes and warrant signatures, then switch traffic. Never overwrite the only
known-good backup. Record the drill and measured recovery time.

## Migration and rollback

Create a backup, run reversible migration checks, deploy canary, verify schema compatibility and old
warrant verification, then promote. On failure, stop writes, revert application, run the documented
down migration where safe, restore if integrity differs, and verify hashes.

## Release gates

Ruff, strict mypy, schemas, traceability, full tests/coverage, AnswerableBench, build, clean install,
dependency/security scans and CodeQL must pass. Critical causal-safety violations must equal zero.
