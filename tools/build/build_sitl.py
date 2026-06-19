#!/usr/bin/env python3
"""
Build and prep SITL for debugging/autotesting/distributing

build_sitl.py --list
build_sitl.py [options]

"""
import shutil
import argparse
from pathlib import Path

import common
from common import CXPILOT_ROOT, CXPILOT_CORE_ROOT
common.add_config_tools_to_path()
import sitl_tools  # noqa: E402


def build_sitl(debug: bool = False, waf_build_opts: list[str] = []) -> None:
    """
    Build SITL binary.
    """
    waf_args = [
        "./waf", "configure",
        "--board=sitl",
        "--define", f"AP_CUSTOM_FIRMWARE_STRING=\"{common.get_cx_version()}\"",
        "--define", "HAL_STORAGE_SIZE=32768",  # Match CubeOrangePlus FRAM
    ]
    if debug:
        waf_args.append("--debug")
    common.run_cmd(waf_args, cwd=CXPILOT_CORE_ROOT)
    waf_args = ["./waf", "plane"]
    waf_args.extend(waf_build_opts)
    common.run_cmd(waf_args, cwd=CXPILOT_CORE_ROOT)


def _frame_cwd(frame_name: str) -> Path:
    """
    Get the path to the cwd that will be used to run the SITL binary.
    """
    return CXPILOT_ROOT / "sitl" / frame_name


def _model_json_path(frame_name: str) -> Path:
    """
    Get the path to the model JSON file for the given frame name.
    """
    return _frame_cwd(frame_name) / f"{frame_name}.json"


def copy_model_json(frame_name: str, symlink: bool = False) -> None:
    """
    Copy the model JSON into the destination folder.
    """
    frame_info = sitl_tools.get_frames()[frame_name]
    _, src = sitl_tools.get_model(frame_info)
    if not src:
        return  # No model JSON to copy
    # Copy model JSON
    dest = _model_json_path(frame_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if symlink:
        if dest.is_symlink() or dest.exists():
            dest.unlink()
        dest.symlink_to(src)
    else:
        shutil.copy(src, dest)


def get_model(frame_name: str) -> str:
    """
    Get the model name to pass with -M to the SITL binary.
    """
    model, json_src = sitl_tools.get_model(sitl_tools.get_frames()[frame_name])
    if not json_src:
        return model  # No model JSON, just return the model name
    # Change the path to be relative to the SITL's cwd
    json_dest = _model_json_path(frame_name)
    return f"{model}:{json_dest.relative_to(_frame_cwd(frame_name))}"


def main():
    parser = argparse.ArgumentParser(description="Build and prep SITL for debugging/autotesting/distributing")
    parser.add_argument("--list", action="store_true", help="List available frames and exit")
    parser.add_argument("--get-model", help="Get the model name to pass with -M to the SITL binary")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--clean-runtime", action="store_true", help="Delete the runtime directories")
    parser.add_argument("--symlinks", action="store_true", help="Use symlinks instead of copying scripts/model.json")
    parser.add_argument("--no-build", action="store_true", help="Skip building SITL binary")
    parser.add_argument("--jobs", "-j", type=int, help="Number of parallel build jobs (passed to waf)")

    args = parser.parse_args()

    frames = sitl_tools.get_frames().keys()
    if args.list:
        for frame in sorted(frames):
            print(frame)
        return

    if args.get_model is not None:
        if args.get_model not in frames:
            raise ValueError(f"Unknown frame: {args.get_model}")
        print(get_model(args.get_model))
        return

    if args.clean_runtime:
        runtime_dir = CXPILOT_ROOT / "sitl"
        if runtime_dir.exists():
            shutil.rmtree(runtime_dir)
            print(f"Deleted runtime directory: {runtime_dir}")

    # Build
    if not args.no_build:
        waf_build_opts = []
        if args.jobs:
            waf_build_opts.append(f"-j{args.jobs}")
        build_sitl(debug=args.debug, waf_build_opts=waf_build_opts)

    # Prep runtime directories
    for frame in frames:
        print(f"Processing frame: {frame}")
        frame_dir = CXPILOT_ROOT / "sitl" / frame
        frame_dir.mkdir(parents=True, exist_ok=True)

        # Process default parameters
        sitl_tools.write_defaults_file(
            frame,
            defaults_out=frame_dir / "defaults.parm",
            strip=args.symlinks,
        )

        # Process model JSON
        copy_model_json(frame, symlink=args.symlinks)

        # Copy scripts
        scripts_dir = frame_dir / "scripts"
        if scripts_dir.exists():
            shutil.rmtree(scripts_dir)  # Clean up existing scripts first, so we don't get stale files after a rename
        sitl_tools.copy_scripts(
            frame,
            dest_root=frame_dir / "scripts",
            symlink=args.symlinks,
        )


if __name__ == "__main__":
    main()
