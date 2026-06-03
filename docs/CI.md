# Build CI

Builds aircraft firmware bundles and CPNs, publishes artifacts to S3, and
reports status back to PRs across repos.

## Topology

Repos

- cxpilot: main integration glue and workflow host
- cxpilot-core: ArduPilot with minimal Carbonix patches
- cxpilot-config: parameter and lua script management

Some changes are expected to span more than one repo. When that happens, use
**identical branch names** on each repo and open PRs for all of them. The CI
system detects matching names and checks out those branches on every repo where
they exist. Any update to any of those PRs triggers a new build and cancels any
in-progress build for that feature branch.

## Triggers

There are three event types that trigger a build. All of them set two variables
that control which commits are checked out in the three repos:

- feature_branch (optional): checked out wherever that branch exists
- base_ref: fallback for any repo missing the feature branch (or when none is
  provided)

1) External builds from core/config PRs
    - Submodule PRs call `actions.createWorkflowDispatch` on this repo
    - `ref`: base branch of the PR
    - Input `feature_branch`: head branch name
    - Can also be triggered manually from the Actions tab, with any supplied
      `ref` and `feature_branch`

2) Integration PRs on this repo
    - Standard `pull_request` trigger on `cxpilot`  
    - Uses the PR base and head the same way as external builds  

3) Release builds on this repo
    - Triggered by `release: published`  
    - Uses the release tag as the ref, no feature branch  
    - CI verifies that submodule SHAs match the tagged commits

## Variables + Discovery

The initial setup step resolves several variable values and stores them for
later jobs.

- Resolve SHAs for all three repos:
  - Prefer `feature_branch` if it exists
  - Else fall back to the base branch of the dispatching PR
  - Throw an error if `feature_branch` is given but not found in any source
    repo
  - For release triggers, the tag is used as the ref in all repos, and there is
    an additional requirement that the submodule SHAs in integration match the
    tagged commits in core/config

- Get version string from integration `version.txt`

- Build the name for the folder to upload to S3

- Discover parallel-build matrices for autopilot/peripheral firmware:
  - `build_aircraft.py --list --json`
  - `build_cpns.py --list-bases --json`
    - "bases" are the unmodified CPN firmware files before config injection
      (more on that later)

- Build `status-map.json` for posting build pass/fail status back to the commits
  in core/config. This is uploaded as a workflow artifact for a later workflow
  to consume

## Build Aircraft

One parallel runner per aircraft config returned by `build_aircraft.py --list`.
This builds the autopilot firmware and copies some related files (like
`defaults.parm`, `extra_hwdef.dat`, `AFQT/target.xml`, etc).

The build tool is split between the root repository and the config repository.
Everything that depends on folder structure, build command-line, etc is in the
root repo; everything that depends on the aircraft config schema itself is in
the config repo. The config repo is responsible for providing the list of
configs, the `extra_hwdef.dat` and `defaults.parm`.

## Build AP_Periph Bases

This is where it starts to get a little janky, and I apologize for that.

Each CAN peripheral node (CPN) has its own board name and embedded parameter
defaults. Between our two platforms/configs, there dozens of unique CPN
binaries. To build these each in waf (which we previously did) takes a long
time, even with caching, or would require a lot of parallel runners to keep build times reasonable.

However, the firmware compilation is otherwise identical for each CPN of a given board type. At the time of writing, this is

- Carbonix F405 CPNs
- Carbonix F405 CPNs without crystal oscillators (using unstable internal
  clocks).
- Matek L431 nodes installed in the Engine Interface Board (EIB).

Bringing us from dozens of unique CPN binaries down to three base builds.

## Generate Final AP_Periph Binaries

This step takes the base CPN binaries and injects the correct board name and
parameter defaults for each unique CPN. See
[BuildTooling.md](BuildTooling.md) for more details on how this is done.

## SITL Build

This builds the SITL binaries for Windows (Cygwin), and bundles scripts and
defaults for the various configurations in `sitl_frames.json` in the config
repo.

## Tests

Tests for any regressions that core/config changes might cause

- Param checks: compares the param metadata in `cxpilot-core` and sanity checks
  all the parameters in `cxpilot-config`
- Lua error checking: runs ArduPilot's lua static analysis tool against all the
  scripts in `cxpilot-config`
- Autotest: based on the stock ArduPilot test suite; at time of writing, this
  just performs integration tests on our custom lua scripts, but will eventually
  do some amount of flight testing

## Publish

At the end of the workflow, all aircraft builds and generated CPNs are merged
into a single 7z archive and uploaded to S3 (both the archive and the individual
files).

## Dependency Updates

All three repos run Dependabot for the `github-actions` ecosystem
(`.github/dependabot.yml` in each). It watches the third-party `uses:` pins in
the workflow ymls (e.g. `actions/checkout@v5`, `cygwin/cygwin-install-action`)
and opens PRs to bump them. Local composite actions (`./.github/actions/*`) are
not versioned, so Dependabot ignores them.

Updates are grouped into a single PR per repo and scheduled weekly for Monday
07:00 Australia/Sydney (the IANA name, so AEST/AEDT is handled automatically).

`cxpilot-core` is near-stock ArduPilot CI on purpose, and we deliberately run
Dependabot over its upstream workflows too — keeping those actions current is
the point. Note that the github-actions ecosystem scans *all* of
`.github/workflows/`; there is no per-file filter. See
[Rebasing.md](Rebasing.md) for how these bumps interact with upstream rebases.

## Nightly Builds

`nightly.yml` runs on a schedule (weekday mornings Sydney time) and checks
whether any of the three repos have new commits since the last successful
nightly. If so, it dispatches the build workflow against the default branch.

## Status Posting

The `post-status.yml` workflow listens for the build workflow to complete,
checks whether it passed/failed/cancelled, downloads the `status-map.json`
artifact, and posts commit statuses to the relevant repos/commits.
