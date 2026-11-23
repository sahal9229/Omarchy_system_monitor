#!/usr/bin/env bash
# ==============================================================================
# Omarchy System Monitor - Installation Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date +%s)"

echo "=== Installing Omarchy System Monitor ==="

# 1. Ensure target directories exist
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$HOME/.config/omarchy/plugins/sahal.sysmon"
mkdir -p "$HOME/.config/hypr"

# 2. Install Executables into ~/.local/bin
echo "--> Installing executables to ~/.local/bin/..."
cp "$SCRIPT_DIR/bin/omarchy-sysmon" "$HOME/.local/bin/omarchy-sysmon"
cp "$SCRIPT_DIR/bin/omarchy-sysmon-toggle" "$HOME/.local/bin/omarchy-sysmon-toggle"
chmod +x "$HOME/.local/bin/omarchy-sysmon" "$HOME/.local/bin/omarchy-sysmon-toggle"

# 3. Install Desktop Entry and Application Icon
echo "--> Installing desktop launcher and application icon..."
cp "$SCRIPT_DIR/desktop/org.omarchy.SystemMonitor.desktop" "$HOME/.local/share/applications/"
cp "$SCRIPT_DIR/desktop/icons/org.omarchy.SystemMonitor.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/"

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

# 4. Install Omarchy Top Panel Quickshell Widget
echo "--> Installing top-panel widget..."
cp "$SCRIPT_DIR/manifest.json" "$HOME/.config/omarchy/plugins/sahal.sysmon/"
cp "$SCRIPT_DIR/SysmonWidget.qml" "$HOME/.config/omarchy/plugins/sahal.sysmon/"

SHELL_CONFIG="$HOME/.config/omarchy/shell.json"
if [ -f "$SHELL_CONFIG" ]; then
    if ! grep -q '"omarchy.sysmon"' "$SHELL_CONFIG"; then
        echo "--> Backing up shell.json to shell.json.bak.${TIMESTAMP}..."
        cp "$SHELL_CONFIG" "${SHELL_CONFIG}.bak.${TIMESTAMP}"

        # Insert beside omarchy.agents in centerEnd using python
        python3 - <<EOF
import json

config_path = "$SHELL_CONFIG"
with open(config_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

layout = cfg.get("bar", {}).get("layout", {})
center_end = layout.get("centerEnd", [])

# Find index of omarchy.agents
target_idx = -1
for i, item in enumerate(center_end):
    if item.get("id") == "omarchy.agents":
        target_idx = i
        break

sysmon_item = {"id": "omarchy.sysmon"}
if target_idx != -1:
    center_end.insert(target_idx + 1, sysmon_item)
else:
    center_end.append(sysmon_item)

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)

print("--> Successfully added omarchy.sysmon beside omarchy.agents in top panel.")
EOF
    fi
fi

# 5. Register Keyboard Shortcut in ~/.config/hypr/bindings.lua
BINDINGS_FILE="$HOME/.config/hypr/bindings.lua"
if [ -f "$BINDINGS_FILE" ]; then
    if ! grep -q "omarchy-sysmon-toggle" "$BINDINGS_FILE"; then
        echo "--> Backing up bindings.lua to bindings.lua.bak.${TIMESTAMP}..."
        cp "$BINDINGS_FILE" "${BINDINGS_FILE}.bak.${TIMESTAMP}"

        cat >> "$BINDINGS_FILE" << 'EOF'

-- Omarchy System Monitor (Ctrl + Shift + Esc)
o.bind("CTRL + SHIFT + ESCAPE", "System Monitor", "omarchy-sysmon-toggle")
EOF
        echo "--> Added Ctrl + Shift + Esc shortcut to bindings.lua."
        if command -v hyprctl &>/dev/null; then
            hyprctl reload 2>/dev/null || true
        fi
    fi
fi

echo "=== Installation Complete! ==="
echo "You can launch Omarchy System Monitor via:"
echo "  1. Top panel button beside Agent button"
echo "  2. Keyboard shortcut: Ctrl + Shift + Esc"
echo "  3. Application launcher (Super + Space -> 'System Monitor')"
echo "  4. Terminal: omarchy-sysmon"
