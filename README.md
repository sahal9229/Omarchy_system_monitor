# Omarchy System Monitor

![Omarchy System Monitor Preview](preview.png)

A lightweight, native-feeling system monitoring desktop application for **Omarchy Linux (Arch Linux-based)**, inspired by the clean layout and real-time visualization of Windows 11 Task Manager.

Omarchy System Monitor provides real-time system resource telemetry, processor frequencies, memory breakdowns, GPU activity, disk read/write rates, network bandwidth, battery telemetry, process management with safe termination, and read-only hardware temperatures and fan speeds.

> **Important**: This application is strictly a **READ-ONLY** hardware monitoring utility. It never modifies BIOS, firmware cooling policies, or PWM hardware attributes.

---

## Features

- **Windows 11 Task Manager Style Dashboard**: Overview page featuring responsive performance cards with real-time sparklines for CPU, RAM, GPU, Disk, Network, Battery, and Temperature.
- **Deep CPU Telemetry**:
  - Overall utilization and load averages (1m, 5m, 15m) calculated from `/proc/stat` and `/proc/loadavg`.
  - Individual per-core real-time graph grids.
  - Processor model, architecture, physical core count, and logical thread count.
  - Scaling core frequencies (current, min, and max limits).
- **Accurate Memory & Swap Analysis**:
  - Exact Linux memory breakdown: In Use, Available, Completely Free, Buffers, and Cached memory (`/proc/meminfo`).
  - Swap utilization percentage, total capacity, and used swap space.
- **Modular GPU Monitoring**:
  - Automatic vendor detection: Intel Integrated Graphics (i915/xe), AMD Radeon, and NVIDIA.
  - Core activity percentage, current frequency, frequency range, and memory model (Unified vs. Dedicated VRAM).
- **Physical Disk & Filesystem I/O**:
  - Independent real-time graphs for physical Read Speed and Write Speed (MB/s).
  - Storage drive identification and NVMe SSD composite temperature.
  - Partition capacity table with mount points, filesystem types, and utilization progress bars.
- **Network Traffic Telemetry**:
  - Dual live graphs for Download (Receive) and Upload (Transmit) rates.
  - Per-adapter status badges (Ethernet, Wi-Fi, VPN), operational states (`UP`/`DOWN`), and packet counters.
- **Battery & Power Telemetry**:
  - Charge level, charging/discharging states, voltage, wattage draw, and health percentage.
  - Graceful "No Battery Present" status on desktop computers.
- **Hardware Thermal & Fan RPM Monitoring (Strictly Read-Only)**:
  - Enumerate sensors across `/sys/class/hwmon/`: CPU Package/Cores (`coretemp`), SSD (`nvme`), Chipset (`pch`), Wi-Fi (`iwlwifi`).
  - Live Fan RPM telemetry (e.g. Dell SMM fan) with idle detection.
  - Session minimum and maximum recorded extremes.
  - Non-intrusive: zero writes to hardware control registers.
- **Process Manager**:
  - Sortable by CPU usage, Memory (MB), PID, and Process Name.
  - Instant search filter by name or PID.
  - Detailed process inspector (PPID, User, State, Memory %, Runtime, and full command line).
  - Confirmation-based termination dialog with graceful `SIGTERM` (default) and force `SIGKILL` options.
  - Permissions checking: non-root users cannot terminate system-critical processes.
- **Omarchy Desktop Integration**:
  - **Top Panel Button**: Custom Quickshell bar widget placed beside the Agent button.
  - **Keyboard Shortcut**: `Ctrl + Shift + Esc` opens or focuses the window.
  - **Application Launcher**: Native `.desktop` entry and custom vector SVG icon.
  - **Single-Instance Behavior**: Repeated launches immediately focus the existing window.
- **Settings & Customization**:
  - Theme switching: System Default, Dark Theme, Light Theme.
  - Configurable polling intervals (0.5s – 5.0s).
  - Temperature unit toggle (°C / °F).
  - Toggle visibility of individual dashboard cards.

---

## Architecture

```
omarchy-sysmon/
├── bin/
│   ├── omarchy-sysmon             # Application launcher
│   └── omarchy-sysmon-toggle      # Single-instance focus/toggle helper
├── src/
│   ├── app.py                     # Adw.Application (GApplication single-instance)
│   ├── config.py                  # Preferences manager (~/.config/omarchy-sysmon/)
│   ├── collectors/                # Pure Linux interface metric parsers
│   │   ├── base.py                # Base collector & RingBuffer history
│   │   ├── cpu.py                 # /proc/stat, /proc/loadavg, sysfs cpufreq
│   │   ├── memory.py              # /proc/meminfo
│   │   ├── gpu.py                 # Intel DRM sysfs, AMD sysfs, NVIDIA SMI
│   │   ├── disk.py                # /proc/diskstats, statvfs, /proc/mounts
│   │   ├── network.py             # /proc/net/dev, sysfs net operstate
│   │   ├── battery.py             # /sys/class/power_supply/
│   │   ├── sensors.py             # /sys/class/hwmon/ (read-only)
│   │   └── process.py             # /proc/[pid]/ stat, status, cmdline
│   └── ui/                        # Libadwaita & GTK4 UI
│       ├── window.py              # MainWindow with left sidebar & ViewStack
│       ├── widgets/
│       │   ├── graph.py           # Cairo real-time line/area graph
│       │   ├── metric_card.py     # Windows 11 style overview card
│       │   └── stat_row.py        # Reusable key-value row
│       └── pages/                 # Independent monitoring views
│           ├── dashboard.py
│           ├── cpu_page.py
│           ├── memory_page.py
│           ├── gpu_page.py
│           ├── disk_page.py
│           ├── network_page.py
│           ├── battery_page.py
│           ├── sensors_page.py
│           ├── process_page.py
│           └── settings_page.py
├── desktop/                       # XDG Desktop & Icon files
│   ├── org.omarchy.SystemMonitor.desktop
│   └── icons/org.omarchy.SystemMonitor.svg
├── omarchy-plugin/                # Native Omarchy Quickshell bar widget
│   ├── manifest.json
│   └── SysmonWidget.qml
├── tests/                         # Unit tests
│   └── test_collectors.py
├── install.sh                     # Reproducible installer with backup
├── uninstall.sh                   # Clean uninstaller with config restoration
└── README.md
```

---

## Dependencies

Preinstalled on Omarchy Linux:
- `python >= 3.10`
- `python-gobject` (PyGObject)
- `gtk4 >= 4.10`
- `libadwaita >= 1.4`
- `cairo` (Pycairo)
- `hyprland` (Compositor)
- `quickshell` (Omarchy Top Panel)

To install on standard Arch Linux:
```bash
sudo pacman -S python python-gobject gtk4 libadwaita cairo
```

---

## Installation

Run the automated installer script:

```bash
cd /home/xahal/Documents/omarchy/omarchy-sysmon
./install.sh
```

### What `install.sh` Does:
1. Installs `omarchy-sysmon` and `omarchy-sysmon-toggle` into `~/.local/bin/`.
2. Installs the desktop launcher to `~/.local/share/applications/` and icon to `~/.local/share/icons/hicolor/scalable/apps/`.
3. Installs the Quickshell bar plugin into `~/.config/omarchy/plugins/omarchy.sysmon/` and places it beside `"omarchy.agents"` in `~/.config/omarchy/shell.json` (backing up `shell.json` first).
4. Registers `Ctrl + Shift + Esc` in `~/.config/hypr/bindings.lua` (backing up `bindings.lua` first) and reloads Hyprland.

---

## Uninstallation

To remove all created files and restore Omarchy configuration:

```bash
cd /home/xahal/Documents/omarchy/omarchy-sysmon
./uninstall.sh
```

---

## Launching the Application

- **Keyboard Shortcut**: Press `Ctrl + Shift + Esc`.
- **Top Panel**: Click the pulse chart icon (``) in the top panel beside the Agent button.
- **App Launcher**: Press `Super + Space`, type `System Monitor`, and press Enter.
- **Terminal**: Run `omarchy-sysmon` or `omarchy-sysmon-toggle`.

---

## Hardware Compatibility & Limitations

| Hardware / Subsystem | Support Status | Notes |
|---|---|---|
| **Intel Core i7-8665U** | Supported | Full utilization, per-core metrics, scaling frequencies, package & core temperatures. |
| **Intel UHD 620 iGPU** | Supported | Frequency telemetry and activity percentage. Memory marked as "Unified System Memory" (no fake VRAM). |
| **NVIDIA GPUs** | Supported | Uses `nvidia-smi` queries when driver and hardware are present. |
| **AMD GPUs** | Supported | Uses AMDGPU sysfs (`gpu_busy_percent`, `mem_info_vram_*`). |
| **Dell SMM Fan Sensor** | Supported | Live RPM read from hwmon (`fan1_input`). 0 RPM reported accurately when fan is idle. |
| **Fan Speed Control** | **Intentionally Excluded** | Strict read-only policy. Firmware controls cooling. |
| **NVMe SSD Storage** | Supported | Physical read/write sectors from `/proc/diskstats`, composite SSD temperatures. |
| **Battery (`BAT0`)** | Supported | Charge %, voltage, wattage draw, and health percentage. |

---

## Testing

Run the automated collector test suite:

```bash
cd /home/xahal/Documents/omarchy/omarchy-sysmon
python3 -m unittest tests/test_collectors.py
```
