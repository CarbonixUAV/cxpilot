# CxPilot Project Guide

This project maintains Carbonix's customized ArduPilot firmware across three git repositories with coordinated changes.

## Repository Structure

You are working in a **three-repository structure**:

```
cxpilot/                            (integration repo - CI, build orchestration)
├── cxpilot-config/                 (submodule - params, scripts, aircraft configs)
└── cxpilot-core/                   (submodule - ArduPilot with Carbonix patches)
```

**CRITICAL**: These are three **separate git repositories**. Always be explicit about which repo you're operating in.

### What Lives Where

| Repo | Contains |
|------|----------|
| **cxpilot** | CI workflows, build scripts, docs |
| **cxpilot-config** | Aircraft configs (XML), params, Lua scripts, hwdef includes |
| **cxpilot-core** | ArduPilot source + Carbonix patches |

## Git Command Patterns

**Always use `git -C <repo>`** to target the correct repository. Only `cd` when running scripts that require it (e.g., waf inside cxpilot-core). When you do `cd`, explicitly return to the integration root immediately after to avoid confusion:

```bash
# GOOD - explicit repo targeting
git -C cxpilot-config status
git -C cxpilot-core log --oneline -10

# If you must cd, chain commands and return
cd cxpilot-core && ./waf configure ... && ./waf build; cd ..

# Alternative - subshell auto-returns when done
(cd cxpilot-core && ./waf configure ... && ./waf build)
```

Use `pwd` when you need to verify your current location.

**Submodules**: Do NOT use `git submodule update` in the integration repo. Manually check out branches in config/core. (Exception: DO use `git submodule update` inside cxpilot-core for ArduPilot's own submodules.) Submodules are configured with `ignore=all`—they won't appear in integration repo `git status` output.

## Build System Mental Model

The build system has three entry points:

1. **`tools/build/build_aircraft.py`** - Builds flight controller firmware
   - Reads aircraft config XML from cxpilot-config
   - Generates defaults.parm, extra_hwdef.dat, ROMFS_custom/
   - Calls waf in cxpilot-core to build ArduPlane
   - Outputs to `output/<CONFIG>/<BOARD>/`

2. **`tools/build/build_cpns.py`** - Builds CAN peripheral firmware (two-step)
   - Step 1: Build ~3 "base" binaries with dummy board names
   - Step 2: Inject real board names and defaults into bases
   - Outputs to `output/<CONFIG>/<CPN_NAME>/`

3. **`tools/build/build_sitl.py`** - Builds SITL and prepares runtime directories
   - Builds cxpilot-core/build/sitl/bin/arduplane
   - Creates sitl/<FRAME>/ directories with scripts/defaults/models

**Schema abstraction**: Build scripts in `cxpilot/tools/build/` are "dumb orchestration." All XML parsing and schema knowledge lives in `cxpilot-config/tools/ac_config_tools.py` and `sitl_tools.py`.

## Common Workflows

### Making Changes

| Change Type | Location |
|-------------|----------|
| Parameters | `cxpilot-config/aircraft_params/` or `cpn_params/` |
| Lua scripts | `cxpilot-config/scripts/` |
| Hardware defs | `cxpilot-config/hwdef/*.inc` |
| Aircraft configs | `cxpilot-config/aircraft_configuration/*.xml` |
| ArduPilot source | `cxpilot-core/` (rare) |
| Build system | `cxpilot/tools/build/*.py` |
| CI | `cxpilot/.github/workflows/*.yml` |

### Feature Branch Workflow

**Only create branches in repos that need changes.** Keep other repos on base branch.

**Base branch**: Use `gh repo view --json defaultBranchRef -q .defaultBranchRef.name` or check `git branch --show-current`

**Branch naming**: MUST use identical branch names across all repos that have changes. This is REQUIRED for CI cross-repo coordination—CI matches branches by name to build them together. Branch names should come from Jira's "Create branch" tool to ensure consistency.

**Jira ticket requirement**: Almost every change should have a corresponding Jira ticket. If it would appear in a changelog, it needs a ticket. "Anonymous PRs" (no Jira ticket) are allowed for minor tooling updates, documentation fixes, or CI tweaks that don't affect flight code or user-facing behavior. When in doubt, instruct the user to create a ticket.

```bash
# Example: Param change (config only)
git -C cxpilot-config checkout -b feature/SW-723-increase-param-x

# Example: Lua script needing new binding (config + core)
git -C cxpilot-config checkout -b feature/SW-456-new-lua-script
git -C cxpilot-core checkout -b feature/SW-456-new-lua-script

# Example: Anonymous PR (no Jira ticket)
git -C cxpilot checkout -b fix/typo-in-ci-comments
```

**Important**: Open PRs in ALL repos with changes. Orphaned branches can cause test builds to pass but release builds to break.

### Testing Changes

These checks are run in CI, but you can run them locally to catch issues early:

```bash
# Parameter validation (** glob handled by Python; catches .parm and .param)
python cxpilot-config/tools/param_check.py --vehicle=Plane cxpilot-config/aircraft_params/**/*.par*m
python cxpilot-config/tools/param_check.py --vehicle=AP_Periph cxpilot-config/cpn_params/**/*.par*m

# Lua validation
cxpilot-core/Tools/scripts/run_luacheck.sh cxpilot-config/scripts

# Build test (pick one config)
python tools/build/build_aircraft.py --config Ottano_AC_3

# SITL autotests (if scripts changed)
python cxpilot-config/tools/cx_autotest.py --build
```

## CI Behavior

**Triggers**: PRs, workflow_dispatch, release tags

**Cross-repo coordination**: CI checks for matching branch names across all repos and builds them together. Build results post back to all matching branches.

**Artifacts**: S3 and GitHub (7z bundles, SITL executables)

## Git Conventions

- **Commit messages**: 50 characters max for summary line
- **No Co-Authored-By**: These are stripped per user preference

## Common Pitfalls

1. **Using `git submodule update` in integration repo** - Don't. Check out branches manually in config/core.

2. **Forgetting to branch all affected repos** - CI expects matching branch names across repos

3. **Editing wrong schema location** - XML schema logic belongs in `cxpilot-config/tools/`, not `cxpilot/tools/build/`

## Quick Reference

```bash
# List available aircraft configs
python tools/build/build_aircraft.py --list

# List available CPN bases
python tools/build/build_cpns.py --list-bases

# List SITL frames
python tools/build/build_sitl.py --list

# Check all three repos for current branches
git branch --show-current
git -C cxpilot-config branch --show-current
git -C cxpilot-core branch --show-current

# Check all repos for uncommitted changes (from integration root)
git status --short
git -C cxpilot-config status --short
git -C cxpilot-core status --short
```

## Further Reading

- [docs/BuildTooling.md](../docs/BuildTooling.md) - Detailed build system explanation
- [docs/CI.md](../docs/CI.md) - CI topology and triggers
- [docs/Rebasing.md](../docs/Rebasing.md) - How to rebase to newer ArduPilot versions
- [docs/Releases.md](../docs/Releases.md) - Release process
- [README.md](../README.md) - Getting started guide
