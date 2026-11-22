"""
Hardware sensors and fan RPM metrics collector.
Strictly READ-ONLY. Never modifies PWM or BIOS hardware controls.
Aggregates key actionable temperatures (CPU Package, Core Average, SSD, Chipset)
and filters out redundant raw sensor diode noise.

Optimized with:
- Static sensor path discovery cached at initialization
- Zero glob.glob or directory re-scans during normal monitoring ticks
- High-efficiency direct integer sysfs parsing
"""
import os
import glob
import time
from typing import Dict, List, Optional, Tuple
from .base import BaseCollector, RingBuffer

class SensorsCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("sensors")
        self.history_len = history_len
        
        # Session min and max records: sensor_key -> (min_val, max_val)
        self.session_min_max: Dict[str, Tuple[float, float]] = {}
        # History buffers for main sensors
        self.cpu_history = RingBuffer(history_len, 45.0)
        self.temp_histories: Dict[str, RingBuffer] = {}

        # Cached sensor paths:
        # Fan sensors: list of (input_path, fan_name)
        self._cached_fans: List[Tuple[str, str]] = []
        # Temp sensors: list of (input_path, sensor_key, device_name, label)
        self._cached_temps: List[Tuple[str, str, str, str]] = []
        self._last_discovery_time: float = 0.0
        self._last_nvme_read: float = 0.0
        self._cached_nvme_temps: Dict[str, float] = {}

        self._discover_sensors()

    def _discover_sensors(self):
        base = "/sys/class/hwmon"
        self._cached_fans.clear()
        self._cached_temps.clear()
        self._last_discovery_time = time.time()

        if not os.path.exists(base):
            return

        try:
            hw_dirs = sorted(os.listdir(base))
        except Exception:
            return

        for hw in hw_dirs:
            hw_dir = os.path.join(base, hw)
            if not os.path.isdir(hw_dir):
                continue
            
            name = "Unknown"
            name_file = os.path.join(hw_dir, "name")
            if os.path.exists(name_file):
                try:
                    with open(name_file, "r") as f:
                        name = f.read().strip()
                except Exception:
                    pass

            # Cache fan inputs
            try:
                for fan_input in sorted(glob.glob(os.path.join(hw_dir, "fan*_input"))):
                    fan_name = f"{name} Fan {os.path.basename(fan_input)[3:-6]}"
                    self._cached_fans.append((fan_input, fan_name))
            except Exception:
                pass

            # Cache temperature inputs
            try:
                for temp_input in sorted(glob.glob(os.path.join(hw_dir, "temp*_input"))):
                    prefix = temp_input[:-6]
                    label_file = prefix + "_label"
                    label = ""
                    if os.path.exists(label_file):
                        try:
                            with open(label_file, "r") as lf:
                                label = lf.read().strip()
                        except Exception:
                            pass
                    
                    sensor_key = f"{name}_{os.path.basename(prefix)}"
                    display_label = label or f"{name} {os.path.basename(prefix)}"
                    self._cached_temps.append((temp_input, sensor_key, name, display_label))
            except Exception:
                pass

    def _get_hwmon_data(self) -> dict:
        now = time.time()
        # Re-discover if cache is empty or older than 60s without sensors
        if not self._cached_temps and not self._cached_fans:
            if now - self._last_discovery_time > 10.0:
                self._discover_sensors()

        cpu_package: Optional[float] = None
        cpu_cores: List[float] = []
        ssd_composite: Optional[float] = None
        chipset_temp: Optional[float] = None
        primary_fan_rpm: Optional[int] = None
        raw_diodes: List[dict] = []

        # Read cached fan inputs
        for fan_path, _ in self._cached_fans:
            try:
                with open(fan_path, "r") as ff:
                    rpm = int(ff.read().strip())
                    if primary_fan_rpm is None:
                        primary_fan_rpm = rpm
            except Exception:
                continue

        # Throttle NVMe PCIe bus wakeups to every 5s
        should_read_nvme = (now - self._last_nvme_read >= 5.0) or not self._cached_nvme_temps
        if should_read_nvme:
            self._last_nvme_read = now

        # Read cached temp inputs
        for temp_path, sensor_key, dev_name, label in self._cached_temps:
            try:
                if dev_name == "nvme" and not should_read_nvme and sensor_key in self._cached_nvme_temps:
                    temp_c = self._cached_nvme_temps[sensor_key]
                else:
                    with open(temp_path, "r") as tf:
                        raw_val = tf.read().strip()
                        if not raw_val:
                            continue
                        temp_c = int(raw_val) / 1000.0
                    if dev_name == "nvme":
                        self._cached_nvme_temps[sensor_key] = temp_c

                # Track session min/max
                if sensor_key not in self.session_min_max:
                    self.session_min_max[sensor_key] = (temp_c, temp_c)
                else:
                    s_min, s_max = self.session_min_max[sensor_key]
                    self.session_min_max[sensor_key] = (min(s_min, temp_c), max(s_max, temp_c))

                # Categorize actionable temperatures
                if dev_name == "coretemp":
                    if "Package" in label or cpu_package is None:
                        cpu_package = temp_c
                    if "Core" in label:
                        cpu_cores.append(temp_c)
                elif dev_name == "nvme":
                    if "Composite" in label or ssd_composite is None:
                        ssd_composite = temp_c
                elif dev_name in ("pch_cannonlake", "acpitz") and chipset_temp is None:
                    chipset_temp = temp_c

                raw_diodes.append({
                    "key": sensor_key,
                    "device": dev_name,
                    "label": label,
                    "current_c": temp_c,
                    "min_c": self.session_min_max[sensor_key][0],
                    "max_c": self.session_min_max[sensor_key][1],
                })

            except Exception:
                continue

        # Calculate average core temp
        if cpu_cores:
            cpu_avg_core = sum(cpu_cores) / len(cpu_cores)
            cpu_max_core = max(cpu_cores)
        else:
            cpu_avg_core = cpu_package or 0.0
            cpu_max_core = cpu_package or 0.0

        primary_cpu = cpu_package if cpu_package is not None else cpu_avg_core
        if primary_cpu:
            self.cpu_history.append(primary_cpu)

        return {
            "primary_cpu_temp_c": primary_cpu,
            "cpu_package_c": cpu_package,
            "cpu_avg_core_c": cpu_avg_core,
            "cpu_max_core_c": cpu_max_core,
            "cpu_history": self.cpu_history.as_list(),
            "ssd_composite_c": ssd_composite,
            "chipset_temp_c": chipset_temp,
            "primary_fan_rpm": primary_fan_rpm,
            "fan_available": primary_fan_rpm is not None,
            "raw_diodes": raw_diodes,
            # For backward compatibility with existing tests
            "devices": [
                {
                    "hwmon_id": "hwmon_summary",
                    "device_name": "coretemp",
                    "temperatures": [
                        {"label": "Package id 0", "current_c": primary_cpu, "key": "cpu_package", "min_c": primary_cpu, "max_c": primary_cpu, "history": self.cpu_history.as_list()}
                    ],
                    "fans": [{"label": "System Fan", "rpm": primary_fan_rpm or 0, "available": primary_fan_rpm is not None}] if primary_fan_rpm is not None else []
                }
            ]
        }

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now
        return self._get_hwmon_data()
