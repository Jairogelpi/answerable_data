# Contributing to Answerable

Answerable treats specifications and tests as product code.

## Development workflow

1. Read `docs/PRODUCT_SPEC.md`.
2. Select a bounded requirement cluster from `requirements/traceability.yaml`.
3. Add a failing test whose name includes the requirement ID.
4. Implement the smallest conforming behavior.
5. Run `make verify`.
6. Update traceability without marking a requirement verified until CI proves it.
7. Open a focused pull request using the repository template.

## Commit and pull-request rules

- Use a branch named `feature/...`, `fix/...`, or `docs/...`.
- Keep unrelated changes in separate pull requests.
- Use Conventional Commit-style subjects.
- Do not weaken a test or quality threshold in the same change that needs it to pass.
- Public schema changes require an ADR and compatibility tests.
- Generated claims and verdict rules require adversarial tests.

## Definition of done

A change is complete only when formatting, linting, typing, unit tests, contract tests, coverage,
and the traceability check pass from a clean checkout.

