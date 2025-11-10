# Release Process

Prior to merging the release PR, merge all open PRs (for that release) in
core/config. Tag the latest commit in each repo with the release tag (e.g.,
`CxPilot-7.3.0`). Then open a release PR in the root `cxpilot` repo with two commits:

- The first commit updates:
  - `version.txt` to drop the `-dev` suffix
  - `ReleaseNotes.txt`
  - submodule SHAs for core/config to point to the tagged commits
      (this ensures that releases can simply be recursively checked out)
- The second commit bumps `version.txt` to the next `-dev` version
  (e.g. `CxPilot-7.4.0-dev`).

This means that the PR's artifact will claim to be the next `-dev` version, but
that is by design. This ensures that the only build generated in CI that *ever*
claims to be a release version is the one built from the tagged commit after
merging the release PR.

After merging the release PR, tag the first commit with the release tag, and
then manually create the GitHub release against that tag. That will trigger CI
to publish the release artifacts to the release folder in S3.

## Notes

This procedure is not enforced in CI on the release PR (though it should some
day). The Build CI does enforce the tag/submodule SHA match when building
though.
