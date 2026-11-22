"""
Battery metrics collector.
Parses /sys/class/power_supply/ for battery properties.
Detects desktop vs laptop systems gracefully.

Optimized with:
- Cached sysfs battery directory and property paths
- 4-second throttling for slow-changing chemical battery capacity
"""
import os
import time
from typing import Optional
from .base import BaseCollector

class BatteryCollector(BaseCollector):
    def __init__(self):
        super().__init__("battery")
        self.battery_path: Optional[str] = None
        self._cached_result: dict = {
            "present": False,
            "percentage": None,
            "status": "Unavailable",
            "health_percent": None,
            "voltage_v": None,
            "power_w": None,
            "time_remaining_sec": None,
            "model_name": None,
            "technology": None,
        }
        self._last_poll_time: float = 0.0
        self._find_battery()

    def _find_battery(self):
        base_dir = "/sys/class/power_supply"
        if not os.path.exists(base_dir):
            self.available = False
            return

        try:
            for entry in sorted(os.listdir(base_dir)):
                full_path = os.path.join(base_dir, entry)
                type_path = os.path.join(full_path, "type")
                if os.path.exists(type_path):
                    with open(type_path, "r") as f:
                        if f.read().strip() == "Battery":
                            self.battery_path = full_path
                            self.available = True
                            return
        except Exception:
            pass
        self.available = False

    def _read_file_str(self, filename: str) -> Optional[str]:
        if not self.battery_path:
            return None
        p = os.path.join(self.battery_path, filename)
        try:
            with open(p, "r") as f:
                return f.read().strip()
        except Exception:
            return None

    def _read_file_int(self, filename: str) -> Optional[int]:
        val = self._read_file_str(filename)
        if val is not None:
            try:
                return int(val)
            except ValueError:
                pass
        return None

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        if not self.battery_path or not self.available:
            return self._cached_result

        # Throttle battery sampling to every 4 seconds
        if self._last_poll_time > 0 and (now - self._last_poll_time < 4.0):
            return self._cached_result

        self._last_poll_time = now

        capacity = self._read_file_int("capacity")
        status = self._read_file_str("status") or "Unknown"
        model = self._read_file_str("model_name")
        tech = self._read_file_str("technology")

        voltage_uV = self._read_file_int("voltage_now")
        voltage_v = (voltage_uV / 1_000_000.0) if voltage_uV else None

        current_uA = self._read_file_int("current_now")
        power_uW = self._read_file_int("power_now")

        power_w: Optional[float] = None
        if power_uW is not None:
            power_w = power_uW / 1_000_000.0
        elif current_uA is not None and voltage_v is not None:
            power_w = (current_uA / 1_000_000.0) * voltage_v

        charge_full = self._read_file_int("charge_full") or self._read_file_int("energy_full")
        charge_full_design = self._read_file_int("charge_full_design") or self._read_file_int("energy_full_design")
        charge_now = self._read_file_int("charge_now") or self._read_file_int("energy_now")

        health_pct: Optional[float] = None
        if charge_full and charge_full_design and charge_full_design > 0:
            health_pct = min(100.0, (charge_full / charge_full_design) * 100.0)

        time_remaining_sec: Optional[float] = None
        if status == "Discharging" and charge_now and current_uA and current_uA > 0:
            time_remaining_sec = (charge_now / current_uA) * 3600.0
        elif status == "Charging" and charge_full and charge_now and current_uA and current_uA > 0:
            rem_charge = max(0, charge_full - charge_now)
            time_remaining_sec = (rem_charge / current_uA) * 3600.0

        self._cached_result = {
            "present": True,
            "percentage": capacity,
            "status": status,
            "health_percent": health_pct,
            "voltage_v": voltage_v,
            "power_w": power_w,
            "time_remaining_sec": time_remaining_sec,
            "model_name": model,
            "technology": tech,
        }
        return self._cached_result
