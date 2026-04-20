# Mutation-testing cache — how it works in kitchen

**Short version:** kitchen does not need a seeding ceremony. The first cold run of the Tier-1 scope on main completed in **2m49s** (790 mutants, 415 killed, 276 survived). Every subsequent run — PR or push — uses `actions/cache@v4` with a `mutmut-refs/heads/main-` fallback to hydrate from the last main-branch run.

This doc exists for the case where the Tier-1 scope grows large enough that a cold run exceeds the 60-minute job timeout, at which point a seeding ceremony becomes necessary. That threshold hasn't been reached and isn't expected in the near term.

## Why no ceremony today

The "enterprise-seeded baseline" procedure (originally documented from `infra-kitchen-gcp/docs/testing/CROSS_REPO_PROMPT.md`) is a Stryker pattern where cold mutation runs routinely take hours because of static-mutant explosion in JavaScript codebases. For mutmut on a 4-service Python scope there is no static-mutant equivalent — the cold run is small enough that the default 60-minute timeout is generous.

PR #29 executed the 360-min-bump procedure unnecessarily. The follow-up fix dropped `timeout-minutes` back to 60 and corrected an independent bug: the cache path was `.mutmut-cache/` (mutmut 2 layout), which does not exist at runtime under mutmut 3.x. Cache writes were silently failing. The path is now `mutants/` — mutmut 3's actual state directory.

## Cache flow today

```
push: main     →  actions/cache@v4 saves mutants/ under key mutmut-refs/heads/main-<sha>
pull_request   →  actions/cache@v4 restores the most recent mutmut-refs/heads/main- key
                  (via restore-keys fallback); mutmut run does incremental work only
```

Forked PRs cannot read the cache across repo boundaries. All Vianda repos are private, so no impact today.

## When you would actually need to seed

If, after enlarging `[tool.mutmut].paths_to_mutate` in `pyproject.toml`, a cold main-branch run starts approaching 60 minutes:

1. Open a PR that bumps `timeout-minutes: 60` → a value that comfortably covers the new cold run time (GitHub's hard cap is 360 minutes).
2. Merge. The `push: main` run kicks off under the elevated timeout and writes the cache.
3. Confirm:

   ```bash
   gh cache list --limit 20 | grep "mutmut-refs/heads/main-"
   ```

   The cache row is typically tens to hundreds of MB once `mutants/` contains results for every file in scope.
4. Open a revert PR dropping `timeout-minutes` back to 60. Subsequent PRs restore from the seeded cache and finish in minutes.

## Drift check

The `pull_request` and `push: main` triggers in `mutation.yml` have a `paths:` filter that must stay in sync with `[tool.mutmut].paths_to_mutate` in `pyproject.toml`:

- Add a file to `paths_to_mutate` → add it to both `paths:` blocks in the workflow.
- Shrink scope → shrink both.

Drift means either under-run (silent coverage loss: a mutated file's PRs skip the job) or over-run (workflow fires when the mutated code didn't change).

## Also watch out for

- **mutmut version bumps.** Major upgrades have changed the cache layout (2.x → 3.x moved from `.mutmut-cache/` to `mutants/`). If a future mutmut version changes the state directory again, `actions/cache@v4` will silently warn `Path does not exist` and cache writes stop. Check the post-run logs for that warning on the first push-to-main after a bump.
- **Forked PRs.** Cache is not shared across repo boundaries. If Vianda ever open-sources a repo running this workflow, expect cold runs on community PRs.
