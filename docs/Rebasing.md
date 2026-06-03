# Rebasing to a newer ArduPilot

The major version number in CxPilot is an indicator of which stable version of
ArduPilot it is based on. This started with CxPilot-5, which was based on 4.3.
CxPilot-6 would have been 4.4, but we skipped straight to CxPilot-7 based on
4.5.

This three-repo structure for CxPilot was built around the end of CxPilot-7
to make all future rebase efforts much easier, by separating our configuration
and lua changes from the core ArduPilot code changes.

## CxPilot-Core

Rebasing CxPilot from 4.5 to 4.6 is not as simple as calling `git rebase
ArduPilot-4.6`. The stable branch always contains a substantial number of
backports which inevitably lead to merge conflicts. By definition, those
backports never need to be rebased forward.

Instead, we

- Generate the list of commits from CxPilot to cherry-pick
- Cherry pick those commits

### Commit list

`git log --oneline --cherry-pick --right-only Plane-4.5...CxPilot-7`

This gets all the commits that appear in CxPilot-7 that don't appear in
Plane-4.5. It skips any "patch-equivalent" commits (commits into the Plane-4.5
branch that were cherry-picked into CxPilot-7) and ignores any merge commits of
4.5 into CxPilot-7.

Redirect the output of this into `tools/rebase/commits.txt` for later.

### Cherry-Picking

`tools/rebase/apply-list.sh` is an interactive helper script to apply and review
each commit in commits.txt. This script was shamelessly vibe-coded, and I really
should make an effort to port this into something that I better understand. I
only dabble in bash, and this script goes beyond my ability to check for subtle
issues.

At each stage, you are given the opportunity to review the patch, review the
commit message, and resolve merge conflicts (if any). Because we aggressively
upstream our work, some of the commits will end up cherry-picking empty. Some
might be not-quite empty, with one or two stray lines; in which case, they are
likely already a part of the new version and should be skipped.

### Double-Checking CarbonixF405

We have this hwdef upstreamed, so they maintain a lot of stuff for us. Double
check the file history at this stage though. Sometimes, they update it in ways
that are NFC, but those changes highlight that we have some feature that we
didn't need. One example of this is `764f6863eafe`.

It's probably a good idea to take this time to confirm that the CarbonixF405 in
master reflects what we want.

### GitHub Actions Dependency Bumps

We run our own Dependabot over core's (near-stock) CI workflows, so we no longer
hand-cherry-pick upstream's dependency-bump commits to keep the trees aligned.
The tradeoff: our Dependabot bumps land as Carbonix-local commits on top of
stock workflow files, so on rebase any workflow file where upstream *also* moved
an action pin will conflict.

When that happens, **prefer upstream's version of the workflow file** rather than
hand-merging version numbers. The next weekly Dependabot run re-bumps anything
left stale, so reconciliation is automatic — don't burn time resolving action
version conflicts during the rebase. See [CI.md](CI.md#dependency-updates) for
the Dependabot setup.

## CxPilot-Config

### Feature Defines

One of the big differences between versions is the list of defines in
`build_options.py`, which is what we use to guide our curated list of features
in our `features.inc` (this lets us get the build size way down, so that if we
ever get a crash dump, it will likely have a lot of useful information in it).
These changes fall into three categories:

1. Existing define renamed
2. New define added to turn off something existing
3. New define added to turn on something (either new, or previously default-off)

There are too many to chase these down individually (at least, going from 4.5 to
4.6 as I'm doing now), so I've added a helper script that turns the output of ArduPilot's `extract_features.py` in a hwdef include so that you can autogenerate `features.inc` from an elf file.

1. Compile the old firmware for one aircraft (e.g. `Ottano_AC_3`)
   - Use `--debug`, as this makes `extract_features.py` work more reliably
     (sometimes the compiler optimizes out the named symbol that the tool is
     looking for)
2. Check out the new `cxpilot-core` branch
3. Run `extract_features_to_hwdef.py` on the old firmware
4. Double check the diff on features.inc and roughly sanity check the new lines.
   Be particularly skeptical of any changes in define values; no values should
   be changing
5. Compile a new firmware and confirm that the output of `extract_features.py`
   matches between new and old
   - If you find any differences, dig into why; it could be a sign of something wrong. Usually it's something benign like the symbol that the tool is looking for in the elf has been renamed, but you need to confirm

**This process is actually a good idea when merging from one stable version to another as well, since new drivers get backported and usually default on.**

Once you have established feature-parity, this is a good time to take another
look at disabling features again. The rebase might have caused some increased
flash usage, and you might want to try to shave it back down. ArduPilot's
existing `test_build_sizes.py` tool is a great way to see which features are
using the most flash. I recommend hacking the script a bit to only test
disabling the features you currently have enabled (in ArduPilot-4.6, there are
351 features, which means 351 individual waf builds to test).

### Other hwdef Headers

For the other `.inc` files in `cxpilot-config/hwdef`, you pretty much just need
to search to confirm that all the defines in there still exist. I do this
manually, as there aren't that many yet. Missing one isn't a huge deal though,
as ArduPilot is good now about adding compiler errors when they migrate to a new
name (e.g., in Cx9, we'll need to change things like `define
HAL_PERIPH_ENABLE_RELAY` to `define AP_PERIPH_RELAY_ENABLED 1`, but you'll get a
really helpful compiler error if you forget)

### Parameters and Lua Scripts

Locally run several CI checks from `cxpilot-build.yml`

- `param_check.py` (for vehicles, CPNs, and SITL)
- `run_luacheck.sh`
- `cx_autotest.py`

This will catch any param renames, lua function changes (or new `luacheck` rules
in general that have been enabled), and the autotest will catch any other
glaring issues that are easy to miss. For example, during the 4.6 rebase, the
autotest caught the fact that 4.6 made SITL's UDP RC protocol (how mavproxy and
autotest send RC commands) was made into a first-class RC backend, which
conflicted with our `RC_PROTOCOLS` parameter, which was explicitly restricting
to just CRSF and SBus.

The last thing to check is the engine-out script. There currently isn't a good
system for autotesting with RealFlight, but I hope to change that someday. This
needs to be manually tested for regressions. It's also probably a good time to
give it another review to see if some old workarounds are still needed.

## Subtle Parameter Issues

There is an edge-case where param names sometimes appear, but are not checked by
the param check: strings in lua/python scripts. We don't have many of these, and
they are unlikely to change (none caught in the 4.6 rebase), but it's worth
checking.

It's hard to programmatically recognize that a string is supposed to be a param
name, but I've made a process that isn't too bad. First, grep for all the
param-looking strings in all lua and python files within cxpilot-config. The
rules for this are:

- Bounded by " or '
- Contains only capital letters, numbers, and underscores
- Starts with a letter
- Contains at least one underscore
- Ends with a letter or number
- Is not on a line that contains `bind_add_param` (so we don't catch
  script-added parameter suffixes)

And dump those into a phoney param file.

```sh
grep -RhP --include='*.py' --include='*.lua' \
  --exclude-dir=cxpilot-core \
  'bind_add_param' -v . \
| grep -oP "['\"][A-Z][A-Z0-9_]*_[A-Z0-9]*[A-Z0-9]['\"]" \
| sed "s/^['\"]//; s/['\"]$//" \
| sort -u \
| sed 's/$/,0/' \
> script_strings.parm
```

First, check out the **old branches** in core and config and run a param check on the new file. This will help you remove the false-positives

```sh
python ./cxpilot-config/tools/param_check.py script_strings.parm \
   --vehicle=Plane \
   --no-bitmask \
   --no-range \
   --no-values
```

Once you remove the false-positives, check the new branches back out and run
again.
