# Threat model

Protected assets are source credentials, tenant data, execution artifacts, evidence graphs, and
issued warrants. Trust boundaries exist at connectors, uploaded files, SQL/Python executors, LLM
providers, API/MCP clients, and exports.

Primary threats and controls:

- cross-tenant access: mandatory tenant context, scoped keys, RBAC, isolation tests;
- credential disclosure: dedicated secret store and telemetry redaction;
- prompt injection: untrusted delimiters, closed schemas, no model-controlled tools or verdicts;
- query/code escape: parsed read-only SQL and expression-only isolated Python;
- evidence/warrant tampering: content hashes, append-only provenance, optional signatures;
- replay/race: idempotency keys and optimistic ETags;
- supply chain: lockfile, dependency review, CodeQL, package build and clean install;
- availability/cost abuse: bounded results, timeouts, cancellation, quotas and circuit breakers.

Residual risk: the expression sandbox is a restricted language boundary, not a general untrusted
Python hosting service. Enterprise connectors require source-side read-only credentials.
