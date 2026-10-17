#!/usr/bin/env bash
# Checks a release tag against pyproject.toml and CHANGELOG.md, then writes the
# matching CHANGELOG entry to <notes-file>. Prints version= and prerelease=
# lines for $GITHUB_OUTPUT. publish.yml runs it; run it locally the same way:
#   .github/scripts/release-check.sh v0.24.0 /tmp/notes.md
set -euo pipefail

usage='usage: release-check.sh <tag> <notes-file>'
tag=${1:?$usage}
notes=${2:?$usage}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

fail() {
  echo "::error::$*" >&2
  exit 1
}

semver='^v((0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-[0-9A-Za-z.-]+)?)$'
[[ $tag =~ $semver ]] || fail "tag $tag is not vX.Y.Z or vX.Y.Z-<prerelease>"
version=${BASH_REMATCH[1]}

declared=$(python3 -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' \
  "$root/pyproject.toml")
[[ $version == "$declared" ]] ||
  fail "tag $tag does not match pyproject.toml version $declared; set version = \"$version\" in a PR before tagging"

[[ -f $root/CHANGELOG.md ]] || fail "CHANGELOG.md is missing; add it with a \"## $version\" entry in a PR before tagging"

# The entry is everything between "## X.Y.Z" (optionally followed by a date)
# and the next "## " heading outside a fenced code block, without leading or
# trailing whitespace-only lines. Fences inside list items are indented.
awk -v heading="## $version" '
  /^[[:space:]]*(```|~~~)/ { fenced = !fenced }
  !fenced && ($0 == heading || index($0, heading " ") == 1) { inside = 1; next }
  inside && !fenced && /^## / { exit }
  inside && /^[[:space:]]*$/ { if (started) blanks++; next }
  inside { for (; blanks > 0; blanks--) print ""; print; started = 1 }
' "$root/CHANGELOG.md" > "$notes"
[[ -s $notes ]] || fail "CHANGELOG.md has no non-empty \"## $version\" entry; add one in a PR before tagging"

echo "version=$version"
if [[ $version == *-* ]]; then echo "prerelease=true"; else echo "prerelease=false"; fi
