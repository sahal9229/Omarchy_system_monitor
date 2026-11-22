"""
Hardware sensors and fan RPM metrics collector.
Strictly READ-ONLY. Never modifies PWM or BIOS hardware controls.
Aggregates key actionable temperatures (CPU Package, Core Average, SSD, Chipset)
and filters out redundant raw sensor diode noise.
"""
import os
import glob
import time
from typing import Dict, List, Optional
from .base import BaseCollector, RingBuffer

class SensorsCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("sensors")
        self.history_len = history_len
        
        # Session min and max records: sensor_key -> (min_val, max_val)
        self.session_min_max: Dict[str, tuple] = {}
        # History buffers for main sensors
        self.cpu_history = RingBuffer(history_len, 45.0)
        self.temp_histories: Dict[str, RingBuffer] = {}

    def _get_hwmon_data(self) -> dict:
        base = "/sys/class/hwmon"
        if not os.path.exists(base):
            return {}

        cpu_package: Optional[float] = None
        cpu_cores: List[float] = []
        ssd_composite: Optional[float] = None
        chipset_temp: Optional[float] = None
        primary_fan_rpm: Optional[int] = None
        raw_diodes: List[dict] = []

        for hw in sorted(os.listdir(base)):
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

            # Check fans (READ ONLY)
            for fan_input in sorted(glob.glob(os.path.join(hw_dir, "fan*_input"))):
                try:
                    with open(fan_input, "r") as ff:
                        rpm = int(ff.read().strip())
                        if primary_fan_rpm is None:
                            primary_fan_rpm = rpm
                except Exception:
                    continue

            # Check temperatures
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

                try:
                    with open(temp_input, "r") as tf:
                        temp_c = int(tf.read().strip()) / 1000.0

                    sensor_key = f"{name}_{os.path.basename(prefix)}"

                    # Track session min/max
                    if sensor_key not in self.session_min_max:
                        self.session_min_max[sensor_key] = (temp_c, temp_c)
                    else:
                        s_min, s_max = self.session_min_max[sensor_key]
                        self.session_min_max[sensor_key] = (min(s_min, temp_c), max(s_max, temp_c))

                    # Filter and extract actionable temps
                    if name == "coretemp":
                        if "Package" in label or not cpu_package:
                            cpu_package = temp_c
                        if "Core" in label:
                            cpu_cores.append(temp_c)
                    elif name == "nvme":
                        if "Composite" in label or ssd_composite is None:
                            ssd_composite = temp_c
                    elif name in ("pch_cannonlake", "acpitz") and chipset_temp is None:
                        chipset_temp = temp_c

                    raw_diodes.append({
                        "key": sensor_key,
                        "device": name,
                        "label": label or f"{name} {os.path.basename(prefix)}",
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

        # Primary CPU temp to track
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
