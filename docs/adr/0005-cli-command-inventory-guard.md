# ADR-0005: A registered-command inventory test guards against silent CLI fallthrough

- Status: Implemented
- Date: 2026-09-18
- Decision owners: Jairo Gelpi Moreno
- Related requirements: FR-CLI-001

## Context

ADR 0004 fixed the bug where `frame`, `plan`, `execute`, `inspect`, `source
add/test` and `warrant show/export` reported exit 0 / `status: ok` without
performing any operation, and closed it with an explicit fail-closed dispatch
in `cli.main`. That fix addressed the symptom on the commands that existed
at the time.

It did not address the process gap that let it ship: 95% branch coverage was
already satisfied by the old catch-all branch, because coverage measures
whether a line executed, not whether it executed correctly. A test asserting
the wrong thing (`code == 0`) also passed, because nothing forced every
registered subcommand to be independently accounted for. If a new subcommand
is added to `build_parser()` in the future and the corresponding dispatch
branch in `main()` is forgotten, the exact same bug class can recur, and
neither the coverage gate nor a per-command test written before the mistake
happened would catch it.

## Decision

Add `test_FR_CLI_001_every_registered_subcommand_is_classified` in
`tests/test_cli_acceptance.py`. It introspects `build_parser()`'s actual
registered subcommand names via argparse's subparsers action (not a
hand-maintained list mirrored from the parser) and asserts that set equals
the union of two explicit, hand-maintained sets in the test file:
`IMPLEMENTED_COMMANDS` (has a real handler and its own acceptance test) and
`RESERVED_COMMANDS` (deliberately unavailable, `COMMANDS` + `source`).

A command present in `build_parser()` but absent from both sets fails the
test immediately, by name, before any behavioral test runs. A command
present in the sets but removed from the parser also fails (keeps the list
from silently drifting stale in the other direction).

This was verified to actually catch the regression class, not just pass
vacuously: a phantom subcommand injected into a patched `build_parser()` at
test time produces the expected `AssertionError` naming it.

## Consequences

Positive: adding a new top-level CLI command without wiring real dispatch or
an explicit "unavailable" classification is now a hard, immediate test
failure with a message naming the exact gap — not a silent fallthrough that
only adversarial testing on a real dataset would surface. This closes the
class of bug, not just the six commands found at the time.

Negative: the two sets are still hand-maintained and could, in principle,
both be wrong in the same way (classify a command as implemented without a
real behavioral test for it). This ADR does not claim that risk is zero,
only that the specific failure mode from ADR 0004 (a command silently
falling through to an `ok` default) cannot recur undetected.

Operational: any future PR that adds a subcommand must touch this test file,
which is the intended forcing function.

## Alternatives considered

- **Rely on branch coverage alone.** Already proven insufficient — it was
  the state before ADR 0004's bug shipped.
- **AST-inspect `cli.main` for an `elif args.command == ...` per registered
  name.** More precise but brittle against refactors (e.g. moving dispatch
  into a dict), and the black-box introspection of the actual parser is
  sufficient to catch the observed failure mode.
- **Do nothing beyond ADR 0004.** Rejected: fixes the instance, not the
  process gap that let it ship past a 95%-coverage, CI-gated repository.
