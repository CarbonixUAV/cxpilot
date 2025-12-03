#!/usr/bin/env python3
# Generate a hwdef.inc file an elf file using ArduPilot's extract_features

import sys
import subprocess
import argparse
from pathlib import Path

EXTRACT_FEATURES_TOOL = Path("./cxpilot-core/Tools/scripts/extract_features.py")


def main():
    arg_parser = argparse.ArgumentParser(description="Extract features from firmware ELF file to hwdef.inc")
    arg_parser.add_argument("elf_file", type=Path, help="Path to the firmware ELF file")
    arg_parser.add_argument("output_hwdef", type=Path, help="Path to output hwdef.inc file")
    args = arg_parser.parse_args()

    elf_file = args.elf_file
    output_hwdef = args.output_hwdef

    if not elf_file.is_file():
        print(f"Error: ELF file '{elf_file}' does not exist.")
        sys.exit(1)

    try:
        result = subprocess.run(
            [sys.executable, str(EXTRACT_FEATURES_TOOL), str(elf_file)],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running extract_features.py: {e.stderr}")
        sys.exit(1)
    features_text = result.stdout

    with output_hwdef.open("w") as hwdef_file:
        lines = features_text.splitlines()
        defines = {}
        for line in lines:
            line = line.strip()
            value = 0 if line.startswith("!") else 1
            define = line.lstrip("!").strip()
            if not define:
                continue
            defines[define] = value
        for define in defines.keys():
            hwdef_file.write(f"undef {define}\n")
        hwdef_file.write("\n")
        for define, value in defines.items():
            hwdef_file.write(f"define {define} {value}\n")

    print(f"Successfully wrote hwdef.inc to '{output_hwdef}'")


if __name__ == "__main__":
    main()
