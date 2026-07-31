# v0.1.0 release checklist

## Automated gates

- [ ] CI passes on Python 3.11 and 3.12.
- [ ] Ruff format and lint pass.
- [ ] Strict mypy passes.
- [ ] Full tests pass with at least 95% coverage.
- [ ] All public schemas validate.
- [ ] Requirement traceability validates.
- [ ] Wheel and sdist build.
- [ ] Wheel installs and imports in a clean virtual environment.
- [ ] CodeQL passes.

## Release integrity

- [ ] Version is 0.1.0 in package metadata and runtime.
- [ ] README examples match actual behavior.
- [ ] CHANGELOG contains 0.1.0.
- [ ] License metadata and LICENSE agree.
- [ ] Tag is annotated and points to the verified main commit.
- [ ] GitHub release contains wheel and sdist with provenance attestation.

## Human review

- [ ] Technical-preview boundary is visible.
- [ ] No unfinished interface is described as production-ready.
- [ ] Security warning and private reporting route are visible.
- [ ] Release notes state known limitations.

Create the tag only after every automated gate is green.
