# Seeding the mutation-testing cache

This is the one-time procedure for populating the main-branch mutmut cache that PR runs restore from. Follow when:

- First wiring up mutation CI.
- Changing `[tool.mutmut].paths_to_mutate` in `pyproject.toml` (invalidates the current cache).
- `mutmut` is upgraded across a major version.

Pattern lifted from the Stryker "enterprise cold-baseline" approach described in `infra-kitchen-gcp/docs/testing/CROSS_REPO_PROMPT.md`; adapted for mutmut.

## Why

`mutmut run` is incremental: it reuses killed-mutant state from `.mutmut-cache/` and only re-mutates what changed. Without a seeded cache, every PR's first run is cold — tens of minutes to hours on Tier-1 scope. The GitHub-hosted runner hard cap is 360 minutes; nothing above that helps.

With a seeded main-branch cache, `actions/cache@v4`'s `restore-keys` fallback hydrates every PR with the main cache, so subsequent runs are seconds-to-minutes on incremental.

## Procedure

1. **Open the seed PR.** Bump `timeout-minutes: 60` to `timeout-minutes: 360` in `.github/workflows/mutation.yml`. Commit with a message making the temporary nature explicit (e.g. `ci(mutation): TEMP 360-min timeout for cache seed — revert in follow-up PR`). Do not change anything else in the same PR.

2. **Merge the seed PR.** The merge triggers a `push: main` run under the elevated timeout. Monitor:

   ```bash
   gh run watch --exit-status
   ```

   Expected wall time: tens of minutes to a couple of hours for Tier-1 scope. If the run hits 360 minutes, the scope is too broad for a single cold run — narrow `paths_to_mutate`, open a separate "shrink scope" PR, merge, then retry seeding.

3. **Confirm the cache was written.**

   ```bash
   gh cache list --limit 20 | grep "mutmut-refs/heads/main-"
   ```

   A row whose key starts with `mutmut-refs/heads/main-` and size is non-trivial (typically tens to hundreds of MB) confirms the cache is hydrated. If no row appears, the run likely failed partway — inspect the logs and re-dispatch.

4. **Open the revert PR.** Drop `timeout-minutes` back to `60`. Merge. Do **not** trigger another `push: main` mutation run from this PR — the change is workflow-only and doesn't touch the mutation scope, so the `paths:` filter on `push: main` will skip the job.

5. **Verify with a real PR.** Open any PR that touches a mutated file. Confirm the mutation job:
   - starts within seconds,
   - logs `Cache restored successfully` (with a restore-key matching `mutmut-refs/heads/main-`),
   - finishes in minutes, not hours.

## Don't do these

- **Don't** raise `timeout-minutes` above 360 — GitHub silently caps at the runner hard limit.
- **Don't** merge the revert PR without waiting for the seed run to finish. If the revert merges first, the next `push: main` uses 60 minutes and the cold seed run dies halfway.
- **Don't** `gh cache delete` the seeded cache casually. If you need to invalidate (e.g. mutmut version bump), repeat the seeding procedure; don't trust that PRs will transparently rebuild it.
- **Don't** try to seed from a forked PR. GitHub Actions cannot write the parent repo's cache from a fork.

## Drift check

The `pull_request` and `push: main` triggers in `mutation.yml` have a `paths:` filter. That list must stay in sync with `[tool.mutmut].paths_to_mutate` in `pyproject.toml`:

- Add a file to `paths_to_mutate` → add it to both `paths:` blocks in the workflow.
- Shrink scope → shrink both.

Drift here means either under-run (silent coverage loss: a mutated file's PRs skip the job) or over-run (workflow fires when the mutated code didn't change).
