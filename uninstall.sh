#!/usr/bin/env bash
# ==============================================================================
# Omarchy System Monitor - Uninstallation Script
# ==============================================================================
set -euo pipefail

echo "=== Uninstalling Omarchy System Monitor ==="

# 1. Remove Executables
echo "--> Removing executables from ~/.local/bin/..."
rm -f "$HOME/.local/bin/omarchy-sysmon"
rm -f "$HOME/.local/bin/omarchy-sysmon-toggle"

# 2. Remove Desktop Entry & Icon
echo "--> Removing desktop launcher and application icon..."
rm -f "$HOME/.local/share/applications/org.omarchy.SystemMonitor.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/org.omarchy.SystemMonitor.svg"

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

# 3. Remove Top Panel Plugin
echo "--> Removing top-panel widget..."
rm -rf "$HOME/.config/omarchy/plugins/omarchy.sysmon"

SHELL_CONFIG="$HOME/.config/omarchy/shell.json"
if [ -f "$SHELL_CONFIG" ] && grep -q '"omarchy.sysmon"' "$SHELL_CONFIG"; then
    echo "--> Removing omarchy.sysmon from shell.json..."
    python3 - <<EOF
import json

config_path = "$SHELL_CONFIG"
with open(config_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)

layout = cfg.get("bar", {}).get("layout", {})
center_end = layout.get("centerEnd", [])
layout["centerEnd"] = [item for item in center_end if item.get("id") != "omarchy.sysmon"]

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)

print("--> Successfully removed omarchy.sysmon from top panel configuration.")
EOF
fi

# 4. Remove Keybinding from ~/.config/hypr/bindings.lua
BINDINGS_FILE="$HOME/.config/hypr/bindings.lua"
if [ -f "$BINDINGS_FILE" ] && grep -q "omarchy-sysmon-toggle" "$BINDINGS_FILE"; then
    echo "--> Removing Ctrl + Shift + Esc binding from bindings.lua..."
    sed -i '/-- Omarchy System Monitor (Ctrl + Shift + Esc)/d' "$BINDINGS_FILE"
    sed -i '/omarchy-sysmon-toggle/d' "$BINDINGS_FILE"
    if command -v hyprctl &>/dev/null; then
        hyprctl reload 2>/dev/null || true
    fi
fi

echo "=== Uninstallation Complete! ==="
echo "All Omarchy System Monitor files and integration hooks have been safely removed."
echo "Your original configuration backups were preserved."
