# Recommended branch protection

Apply the following rules to `main` in GitHub repository settings:

1. Require a pull request before merging.
2. Require at least one approval.
3. Dismiss stale approvals when new commits are pushed.
4. Require conversation resolution.
5. Require branches to be up to date.
6. Require these status checks:
   - `Quality / Python 3.11`
   - `Quality / Python 3.12`
   - `Package`
   - `Analyze Python`
7. Block force pushes and branch deletion.
8. Require linear history or squash merges.
9. Do not allow administrators to bypass checks except for documented incident recovery.

CODEOWNERS currently assigns all paths to `@Jairogelpi`. As the project grows, add specialist owners
for public schemas, statistical methods, security-critical executors, and CI.

