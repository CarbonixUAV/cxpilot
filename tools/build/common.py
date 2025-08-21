"""
Common utilities for build_aircraft and build_cpns scripts.
"""
import os
import sys
import shlex
import functools
import subprocess
from os import PathLike
from pathlib import Path
from typing import Sequence, Optional

CXPILOT_ROOT = Path(__file__).parents[2].resolve()
CXPILOT_CONFIG_ROOT = CXPILOT_ROOT / "cxpilot-config"
CXPILOT_CORE_ROOT = CXPILOT_ROOT / "cxpilot-core"
if not CXPILOT_CORE_ROOT.is_dir():
    raise FileNotFoundError(f"CXPILOT_CORE_ROOT does not exist: {CXPILOT_CORE_ROOT}")
if not CXPILOT_CONFIG_ROOT.is_dir():
    raise FileNotFoundError(f"CXPILOT_CONFIG_ROOT does not exist: {CXPILOT_CONFIG_ROOT}")


# Get the version from version.txt
@functools.lru_cache(maxsize=1)
def get_cx_version() -> str:
    """
    Read the version from the version.txt file.
    The file should contain exactly one non-empty line with the version.
    """
    version_file = CXPILOT_ROOT / "version.txt"
    try:
        lines = [line.strip() for line in version_file.read_text().splitlines() if line.strip()]
    except FileNotFoundError:
        raise FileNotFoundError(f"Version file {version_file} does not exist")

    if len(lines) != 1:
        raise ValueError(f"Version file {version_file} should contain exactly one non-empty line with the version")

    return lines[0]


def add_config_tools_to_path() -> None:
    """
    Add CXPILOT_CONFIG_ROOT/tools to the Python path to allow importing ac_config_tools.
    """
    target = (CXPILOT_CONFIG_ROOT / "tools").resolve()
    if not target.exists():
        raise RuntimeError(f"Missing tools dir: {target}")
    existing = {Path(p).resolve() for p in sys.path if isinstance(p, str)}
    if target not in existing:
        sys.path.insert(0, str(target))  # ensure checkout wins over installed copies


def is_clean_git_repo(path: Path, ignore_submodules: bool = False) -> bool:
    """Check if the git repository at the given path is clean."""
    args = ['git', 'status', '--porcelain']
    if ignore_submodules:
        args.append('--ignore-submodules=all')
    try:
        output = subprocess.check_output(args, cwd=path, text=True)
        return not bool(output.strip())
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error checking git status in {path}: {e}")


def assert_clean_git_all():
    """Check if all three git repositories are clean.

    Check the git status of the repositories. This check is all about ensuring
    we have a reproducible build, so we don't care if the integration repo
    points to different submodule SHAs, since all three will be embedded into
    the ROMFS XML file, but otherwise care if any of these three repositories
    is dirty.
    """
    if not is_clean_git_repo(CXPILOT_ROOT, ignore_submodules=True):
        raise RuntimeError("Integration repository is dirty.")
    if not is_clean_git_repo(CXPILOT_CORE_ROOT):
        raise RuntimeError("cxpilot-core repository is dirty.")
    if not is_clean_git_repo(CXPILOT_CONFIG_ROOT):
        raise RuntimeError("cxpilot-config repository is dirty.")


class CmdError(RuntimeError):
    """
    Exception raised when run_cmd fails.
    """
    def __init__(self, args: Sequence[str], returncode: int, stderr: str):
        super().__init__(f"cmd failed ({returncode}): {shlex.join(args)}\n--- stderr ---\n{stderr}")
        self.args_ = args
        self.returncode = returncode
        self.stderr = stderr


def run_cmd(args: Sequence[str], cwd: Optional[PathLike] = None, env: Optional[dict] = None) -> None:
    """
    Run a command in a subprocess and raise an error if it fails.

    Args:
        args (Sequence[str]): Command and arguments to run.
        cwd (Optional[PathLike]): Working directory to run the command in.
        env (Optional[dict]): Environment variables to set for the command.
    Raises:
        CmdError: If the command fails (non-zero return code).
    """
    print(f"Running command: {shlex.join(args)}")
    if cwd is not None:
        print(f"Working directory: {cwd}")
    if env is not None:
        print(f"Environment: {env}")
        # Merge the provided environment with the current one
        env = {**os.environ, **env}

    proc = subprocess.Popen(args, cwd=cwd, env=env, text=True,
                            stdout=None, stderr=subprocess.PIPE, bufsize=1)
    err_buf = []
    try:
        if proc.stderr is not None:
            for line in proc.stderr:
                sys.stderr.write(line)  # live pass-through
                err_buf.append(line)
    except KeyboardInterrupt:
        proc.kill()
        rc = proc.wait()
        err_buf.append("\n<interrupted>\n")
    finally:
        rc = proc.wait()
    if rc != 0:
        raise CmdError(args, rc, "".join(err_buf))
