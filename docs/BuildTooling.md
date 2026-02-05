# CxPilot Build Tooling

This document describes the build scripts for CxPilot, including preparing
aircraft bundles for firmware update through the Aircraft Final Qualification
Tool (AFQT). It defines expected outputs, commands, and env assumptions for
flight controller firmware, CAN peripherals, and SITL.

## Outputs

### Aircraft Bundles

`build_aircraft.py` and `build_cpns.py` produce outputs in the following structure:

```plaintext
output/<CONFIG>/ 
  <FC_BOARD>/
    <waf firmware outputs>
    defaults.parm                # processed defaults
    extra_hwdef.dat              # processed hwdef modifications
    ROMFS_custom/
      scripts/
      AircraftConfiguration.xml
  <CPN_NAME_1>/
    AP_Periph.bin
    defaults.parm
  <CPN_NAME_2>/
    AP_Periph.bin
    defaults.parm
  AFQT/
    target.xml
  ReleaseNotes.txt
```

### SITL Outputs

`build_sitl.py` produces outputs in the following structure:

```plaintext
sitl/
  <FRAME_1>/
    scripts/
    defaults.parm
    <optional model.json>
  <FRAME_2>/
    scripts/
    defaults.parm
    <optional model.json>
```

Where `<FRAME_N>` corresponds to the frame names defined in `sitl_frames.json`.
These directories contain the necessary files for SITL simulation, and serve as
the working directory for the SITL binary (where `eeprom.bin` and `logs/` etc.
are created).

## Commands

### Build aircraft firmware

```sh
build_aircraft.py [--list]
build_aircraft.py --config <CONFIG> [--debug] [--upload]
build_aircraft.py [--clean] [--waf-clean] [--waf-distclean]
```

The `build_aircraft.py` script is responsible for building ArduPilot firmware
for the flight controller of a specific aircraft configuration (available
configurations can be listed with `--list`). It is used by CI as well as
VSCode's build tasks. It generates a `defaults.parm`, `extra_hwdef.dat`,
assembles a `ROMFS_custom` directory with extra files to embed, and calls `waf`
to generate the firmware. After building, it copies the files into the output
directory structure described above.

For local testing, you can pass `--upload` to build and upload the firmware to
the flight controller and can pass `--debug` to make a debug build for SWD
debugging.

The `output` directory (and `build`, the temporary staging directory) can be
cleaned up with the `--clean` flag. This is not to be confused with `waf clean`,
which can be done by passing `--waf-clean` (and `--waf-distclean` to remove the
core ArduPilot build directory).

### Build CAN peripherals

The `build_cpns.py` script is responsible for building AP_Periph binaries, as
well as packaging them into the output directory structure.

For efficiency, this is done in a two-step process:

1. Build the "base" binaries with `waf`
    - A base binary is a generic AP_Periph build for a specific board type, but
      without the final board name, nor the final `defaults.parm` embedded. These
      builds have a long random dummy string as the board name.
2. Use `cx_apj_tool.py` to edit the base binaries, setting the final board name
   and embedding the final `defaults.parm`.
    - This is done by basically find/replacing the board name in the binary and
      then using ArduPilot's stock `apj_tool.py` to set the `defaults.parm`
    - AP_Periph uses an APP_DESCRIPTOR with a CRC so the bootloader can verify
      the image; the descriptor CRC must be fixed afterward.

This is done because the `waf` build takes surprisingly long to recompile each
time you change the board name and defaults, and there are a large number
of CPNs to compile for. There is a much smaller set of base binaries (currently
three), which helps massively speed up CI.

Example commands:

```sh
build_cpns.py --list-bases
build_cpns.py --list-bases --allow-deprecated
build_cpns.py --list-bases --config <CONFIG>
build_cpns.py --list-bases -c <CONFIG_1> -c <CONFIG_2>
```

Lists all the base binaries needed for all active configurations, or all including deprecated ones, or for specific configurations.

```sh
build_cpns.py --build-base
build_cpns.py --build-base --allow-deprecated
build_cpns.py --build-base --config <CONFIG>
build_cpns.py --build-base -c <CONFIG_1> -c <CONFIG_2>
build_cpns.py --build-base <BASE_NAME>
```

Like with --list-bases, but builds the base binaries. Alternatively, you can
pass a specific base name to build only that one (which is useful for parallel
actions in CI).

```sh
build_cpns.py --generate
build_cpns.py --generate -c <CONFIG>
```

Generates the final CPN firmware with the final board name and `defaults.parm`
embedded and copies them into the output directory structure described above.
This must be run after `--build-base`, or tacked onto the end of any of the
above `--build-base` commands.

### SITL

The `build_sitl.py` script is responsible for building the SITL binary and
preparing the runtime directories (for storing logs, eeprom, etc.) for each
frame defined in `sitl_frames.json`. It also generates a processed `defaults.parm`
for each frame and copies (or symlinks) the necessary scripts into the scripts
directory of each frame.

Example commands:

```sh
build_sitl.py --symlinks
```

Builds the SITL binary and prepares the runtime directories for all frames. The
extra `--symlinks` flag will symlink the scripts and optional model.json files
(used by the headless frames) to their respective source files in git. This
allows you to edit the scripts and have them immediately available in SITL
without needing to rebuild (and prevents you from accidentally editing the copy
and forgetting put the changes back into the source and commit them).

```sh
build_sitl.py --no-build
```

Prepares the runtime directories for all frames without building the SITL binary.

```sh
build_sitl.py --list
```

Lists all the frames defined in `sitl_frames.json`.

```sh
build_sitl.py --get-model=<FRAME>
```

Gets the exact argument to pass to `-M` when running SITL for the given frame.

```sh
build_sitl.py --clean-runtime
```

Deletes all the runtime directories for all frames, including logs, eeprom, etc.
This is useful for cleaning up old logs, terrain, and eeprom files that are no
longer needed.

### Commit Hashes

The SHA of all three repos, as well as the build date, are embedded into the
configuration xml in ROMFS when building. Additionally, ArduPilot embeds the git
commit hash into the firmware binaries, and it is reported to the GCS along with
the firmware version. The embedded commit hash can be overridden by setting
`GIT_VERSION` and `GIT_VERSION_INT` environment variables before building.

Instead of using the hash of the core ArduPilot submodule, we override this with
the hash of the top-level CxPilot repository (the integration repo). For
official releases, the submodule hashes will be committed to the CxPilot
repository and the top-level commit hash will be all the information needed to
identify the exact state of the code used to build a specific version of
CxPilot.

Any repo that has unstaged changes will have a `*` appended to the commit hash.
This is a warning that this build likely cannot be reproduced exactly.
Additionally, for the top-level repo, if either the config or core submodules
are not at the expected commit, a `+` is appended to the commit hash. This is an
indicator that the build can be reproduced, but you need to manually check out
the correct submodules before building.

## Parallelism Notes

The build scripts were not designed with any kind of (local) parallelism in
mind. Do not try to run any of these at the same time as one another on the same
machine. They were designed to run on separate images in CI, where they can run
in parallel without issues.
