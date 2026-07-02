# Changelog entries

Every PR targeting `master` must add at least one file under this directory,
describing the user-facing change. A GitHub Actions workflow
(`.github/workflows/changelog.yml`) enforces this on every pull request.

## Convention

- One file per change. Name it after the Phabricator ticket (`T50530`) or, if
  there is no ticket, a short descriptive slug (`access-log`).
- File content is one or more bullet lines describing the change, e.g.:
  ```
  - [T50530] Bump sentry version
  ```
- Entries are collated into the top-level `CHANGELOG.md` at release time.

## Skipping the check

For docs-only, dependency-bump, or CI-only PRs that need no changelog entry,
add the `no-changelog` label to the PR. The workflow will skip the check.

See `.github/workflows/changelog.yml` for the exact enforcement logic.
