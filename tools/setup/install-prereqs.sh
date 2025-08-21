#!/bin/bash

set -e

#=================================================
#============== Setup VS Code files ==============
#=================================================
VS_DIR="$(dirname "$0")/../../.vscode"
VS_DIR="$(realpath --relative-to="$PWD" "$VS_DIR")"
for SRC in "$VS_DIR"/example.*; do
    BASENAME=$(basename "$SRC" | sed 's/^example\.//')
    DEST="$VS_DIR/$BASENAME"
    if [[ -e "$DEST" ]]; then
        echo "$DEST already exists, skipping."
        continue
    fi
    cp "$SRC" "$DEST"
    echo "Copied $SRC -> $DEST"
done

#=================================================
#=============== .bashrc additions ===============
#=================================================
# If we're running in WSL, we need to store the IP address of the Windows host
# in the environment variable `wslhost`. This is used by build_sitl.py and the
# example launch.json files anywhere where we need the IP address of the Windows
# host (like connecting to RealFlight Link or UDP MAVLink to Mission Planner
# running on Windows).
if grep -qEi "(Microsoft|WSL)" /proc/version; then
    WSLHOST_LINE="export wslhost=\$(ip route list default | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | head -n 1)"
    if  grep -qFx "$WSLHOST_LINE" ~/.bashrc; then
        NEEDS_WSLHOST=false
    else
        NEEDS_WSLHOST=true
    fi
    if [ "$NEEDS_WSLHOST" == true ] && grep -q "^[[:space:]]*export[[:space:]]*wslhost" ~/.bashrc; then
        echo "Different, probably older, definition of wslhost found in ~/.bashrc."
        echo "Do you want to comment it out and add the new definition? (y/N)"
        read -r answer
        if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
            # Comment out existing wslhost definition
            sed -i '/^[[:space:]]*export[[:space:]]*wslhost/ s/^/#/' ~/.bashrc
            echo "Commented out existing wslhost definition in ~/.bashrc"
        else
            NEEDS_WSLHOST=false
        fi
    fi
    if [ "$NEEDS_WSLHOST" == true ]; then
        {
            echo "# IP address for the Windows machine on the virtual network:"
            echo "$WSLHOST_LINE"
        } >> ~/.bashrc
        echo "Added wslhost definition to ~/.bashrc"
    fi
fi
