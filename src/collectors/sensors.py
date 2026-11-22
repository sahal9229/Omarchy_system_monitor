"""
Hardware sensors and fan RPM metrics collector.
Strictly READ-ONLY. Never modifies PWM or BIOS hardware controls.
Enumerates /sys/class/hwmon/ and maintains session min/max records.
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
        self.temp_histories: Dict[str, RingBuffer] = {}

    def _get_hwmon_devices(self) -> List[dict]:
        hwmon_list = []
        base = "/sys/class/hwmon"
        if not os.path.exists(base):
            return hwmon_list

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

            temps = []
            # Find temp*_input files
            for temp_input in sorted(glob.glob(os.path.join(hw_dir, "temp*_input"))):
                prefix = temp_input[:-6] # e.g. .../temp1
                label_file = prefix + "_label"
                label = None
                if os.path.exists(label_file):
                    try:
                        with open(label_file, "r") as lf:
                            label = lf.read().strip()
                    except Exception:
                        pass
                
                if not label:
                    base_num = os.path.basename(prefix)
                    label = f"{name} {base_num}"

                try:
                    with open(temp_input, "r") as tf:
                        temp_c = int(tf.read().strip()) / 1000.0
                        sensor_key = f"{name}_{os.path.basename(prefix)}"
                        
                        # Session min/max
                        if sensor_key not in self.session_min_max:
                            self.session_min_max[sensor_key] = (temp_c, temp_c)
                        else:
                            s_min, s_max = self.session_min_max[sensor_key]
                            self.session_min_max[sensor_key] = (min(s_min, temp_c), max(s_max, temp_c))

                        # History buffer
                        if sensor_key not in self.temp_histories:
                            self.temp_histories[sensor_key] = RingBuffer(self.history_len, temp_c)
                        self.temp_histories[sensor_key].append(temp_c)

                        s_min, s_max = self.session_min_max[sensor_key]
                        temps.append({
                            "key": sensor_key,
                            "label": label,
                            "current_c": temp_c,
                            "min_c": s_min,
                            "max_c": s_max,
                            "history": self.temp_histories[sensor_key].as_list(),
                        })
                except Exception:
                    continue

            fans = []
            # Find fan*_input files (READ ONLY)
            for fan_input in sorted(glob.glob(os.path.join(hw_dir, "fan*_input"))):
                prefix = fan_input[:-6]
                label_file = prefix + "_label"
                label = None
                if os.path.exists(label_file):
                    try:
                        with open(label_file, "r") as lf:
                            label = lf.read().strip()
                    except Exception:
                        pass
                
                if not label:
                    label = f"{name} Fan {os.path.basename(prefix)[3:]}"

                try:
                    with open(fan_input, "r") as ff:
                        rpm = int(ff.read().strip())
                        fans.append({
                            "label": label,
                            "rpm": rpm,
                            "available": True,
                        })
                except Exception:
                    continue

            if temps or fans:
                hwmon_list.append({
                    "hwmon_id": hw,
                    "device_name": name,
                    "temperatures": temps,
                    "fans": fans,
                })

        return hwmon_list

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        devices = self._get_hwmon_devices()

        # Extract primary CPU temp and Fan RPM for quick dashboard access
        primary_cpu_temp: Optional[float] = None
        primary_fan_rpm: Optional[int] = None

        for dev in devices:
            if dev["device_name"] == "coretemp":
                for t in dev["temperatures"]:
                    if "Package" in t["label"] or "temp1" in t["key"]:
                        primary_cpu_temp = t["current_c"]
                        break
            if not primary_cpu_temp and dev["temperatures"]:
                primary_cpu_temp = dev["temperatures"][0]["current_c"]

            for f in dev["fans"]:
                if primary_fan_rpm is None:
                    primary_fan_rpm = f["rpm"]

        return {
            "devices": devices,
            "primary_cpu_temp_c": primary_cpu_temp,
            "primary_fan_rpm": primary_fan_rpm,
            "fan_available": primary_fan_rpm is not None,
        }
