# Contributing

`AGENTS.md` holds the rules for changes to this repository: topic branches and
PRs, the two-step process for breaking changes, and the public-API rule for
tests. `README.md` lists the commands CI runs.

## Changelog

`CHANGELOG.md` has one `## X.Y.Z` section per release, newest first, and a
`## Unreleased` section at the top for changes merged since the last release.
A PR that changes what a Tenant app can observe adds a line under
`## Unreleased`. A release that deprecates or removes something shows the
migration, as `AGENTS.md` requires. The release PR renames `## Unreleased` to
`## X.Y.Z`; that section becomes the GitHub release notes.

## Releasing

Pushing a `vX.Y.Z` tag is the whole release:

1. In a PR, bump `version` in `pyproject.toml` (run `uv lock` so `uv.lock`
   follows) and rename `## Unreleased` in `CHANGELOG.md` to `## X.Y.Z`, or add
   that entry.
2. After it merges, tag the merge commit on `main` and push the tag:
   `git tag vX.Y.Z <merge-commit> && git push origin vX.Y.Z`.

`.github/workflows/publish.yml` then reruns CI and
`.github/scripts/release-check.sh`, which fails unless the tag matches the
`pyproject.toml` version and `CHANGELOG.md` has a non-empty `## X.Y.Z` entry.
It also fails when the tagged commit is not on `main`. Only after every check
passes does it publish to PyPI with trusted publishing (skipped when PyPI
already has the version) and create the GitHub release for the tag. A tag with
a prerelease suffix, such as `v0.25.0-rc.1`, needs the same `pyproject.toml`
version and `CHANGELOG.md` entry, is not published to PyPI, and gets a GitHub
prerelease. Do not create GitHub releases by hand: the workflow leaves an
existing release as it is, notes included.

The PyPI upload cannot be undone. If a check fails, nothing was published:
delete the tag (`git push origin :refs/tags/vX.Y.Z`), fix `main`, and tag
again. Rerunning a failed run is safe: a version PyPI already has and a GitHub
release that already exists are skipped, not recreated.

Before tagging, check a release without publishing anything: run the Publish
workflow from the Actions tab on `main` with the tag you are about to push
(`gh workflow run publish.yml -f tag=vX.Y.Z`). It runs CI, every check, and
the build, and its summary shows what would be published and the release
notes. Locally, `.github/scripts/release-check.sh vX.Y.Z notes.md` runs the
same checks except the one for `main`.

PyPI's trusted publisher for `blazing_agents` is bound to the workflow file
name `publish.yml` and the `pypi` environment. Renaming either breaks
publishing until the publisher is updated on PyPI.
