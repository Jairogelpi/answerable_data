# ADR-0001: Standard-library domain core and SQLite reference persistence

- Status: Accepted
- Date: 2026-07-30
- Decision owner: Jairo Gelpi Moreno
- Related requirements: INV-006, INV-011, FR-LIFE-001 through FR-LIFE-007

## Context

The first three phases establish contracts that every later analytical module will depend on. The
domain must remain deterministic, portable, typed, and testable without a network or service stack.

## Decision

Use frozen Python dataclasses and enums for the domain, canonical JSON for serialization, and SQLite
as the reference transactional repository. Keep ports explicit so hosted deployments can add
PostgreSQL without changing domain behavior.

## Consequences

- The core has no runtime dependency.
- Local tests are fast and deterministic.
- Database behavior can be exercised with real transactions.
- JSON Schema remains an interoperability contract rather than a runtime framework feature.
- A future PostgreSQL adapter must pass the same repository contract suite.

## Alternatives considered

Pydantic and SQLAlchemy provide conveniences but would make the foundational domain dependent on
third-party behavior and complicate isolated verification. They may be used at outer API boundaries
later without becoming the domain source of truth.

