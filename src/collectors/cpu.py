"""
CPU metrics collector.
Parses /proc/stat, /proc/loadavg, /proc/cpuinfo, and /sys/devices/system/cpu.
"""
import os
import time
from typing import Dict, List, Optional
from .base import BaseCollector, RingBuffer

class CPUCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("cpu")
        self.history_len = history_len
        self.overall_history = RingBuffer(history_len, 0.0)
        self.core_histories: List[RingBuffer] = []
        
        # Static info
        self.model_name = "Unknown CPU"
        self.architecture = os.uname().machine
        self.physical_cores = 0
        self.logical_processors = 0
        self._parse_cpuinfo()

        # Initialize core histories
        for _ in range(max(1, self.logical_processors)):
            self.core_histories.append(RingBuffer(history_len, 0.0))

        # Previous tick counters for CPU utilization calculation
        self._prev_total_time = 0
        self._prev_idle_time = 0
        self._prev_core_times: List[tuple] = []
        
        # Initial read to prime delta calculations
        self._prime_counters()

    def _parse_cpuinfo(self):
        core_ids = set()
        physical_ids = set()
        processors = 0
        model = None
        
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="replace") as f:
                current_core_id = None
                current_phys_id = None
                for line in f:
                    line = line.strip()
                    if not line:
                        if current_core_id is not None and current_phys_id is not None:
                            core_ids.add((current_phys_id, current_core_id))
                        current_core_id = None
                        current_phys_id = None
                        continue
                    if line.startswith("model name") and not model:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            model = parts[1].strip()
                    elif line.startswith("processor"):
                        processors += 1
                    elif line.startswith("core id"):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            current_core_id = parts[1].strip()
                    elif line.startswith("physical id"):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            current_phys_id = parts[1].strip()
        except Exception as e:
            self.error = f"Failed to read /proc/cpuinfo: {e}"

        self.model_name = model or "Unknown CPU"
        self.logical_processors = processors or os.cpu_count() or 1
        self.physical_cores = len(core_ids) if core_ids else (self.logical_processors // 2 or 1)

    def _prime_counters(self):
        try:
            with open("/proc/stat", "r") as f:
                lines = f.readlines()
            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "cpu":
                    # cpu  user nice system idle iowait irq softirq steal guest guest_nice
                    values = [int(x) for x in parts[1:8]]
                    self._prev_idle_time = values[3] + values[4] # idle + iowait
                    self._prev_total_time = sum(values)
                elif parts[0].startswith("cpu") and parts[0][3:].isdigit():
                    values = [int(x) for x in parts[1:8]]
                    idle = values[3] + values[4]
                    total = sum(values)
                    self._prev_core_times.append((idle, total))
        except Exception as e:
            self.error = f"Failed to prime /proc/stat: {e}"

    def _get_frequencies(self) -> Dict[str, Optional[float]]:
        freqs = {
            "current_mhz": None,
            "min_mhz": None,
            "max_mhz": None,
            "per_core_mhz": []
        }
        try:
            # Check scaling frequencies in sysfs
            base_dir = "/sys/devices/system/cpu"
            cur_freqs = []
            for i in range(self.logical_processors):
                cur_file = os.path.join(base_dir, f"cpu{i}", "cpufreq", "scaling_cur_freq")
                if os.path.exists(cur_file):
                    with open(cur_file, "r") as f:
                        cur_freqs.append(int(f.read().strip()) / 1000.0)
                else:
                    cur_freqs.append(None)
            
            valid_freqs = [f for f in cur_freqs if f is not None]
            if valid_freqs:
                freqs["current_mhz"] = sum(valid_freqs) / len(valid_freqs)
                freqs["per_core_mhz"] = cur_freqs
            
            # Min/Max
            cpu0_min = os.path.join(base_dir, "cpu0", "cpufreq", "cpuinfo_min_freq")
            cpu0_max = os.path.join(base_dir, "cpu0", "cpufreq", "cpuinfo_max_freq")
            if os.path.exists(cpu0_min):
                with open(cpu0_min, "r") as f:
                    freqs["min_mhz"] = int(f.read().strip()) / 1000.0
            if os.path.exists(cpu0_max):
                with open(cpu0_max, "r") as f:
                    freqs["max_mhz"] = int(f.read().strip()) / 1000.0
        except Exception:
            pass
        return freqs

    def _get_load_averages(self) -> Tuple[float, float, float]:
        try:
            with open("/proc/loadavg", "r") as f:
                parts = f.read().strip().split()
                return float(parts[0]), float(parts[1]), float(parts[2])
        except Exception:
            return 0.0, 0.0, 0.0

    def _get_cpu_temperature(self) -> Optional[float]:
        # Try coretemp hwmon
        try:
            hwmon_root = "/sys/class/hwmon"
            for h in os.listdir(hwmon_root):
                name_path = os.path.join(hwmon_root, h, "name")
                if os.path.exists(name_path):
                    with open(name_path, "r") as f:
                        name = f.read().strip()
                    if name == "coretemp":
                        # Check temp1_input (usually package temp)
                        temp_path = os.path.join(hwmon_root, h, "temp1_input")
                        if os.path.exists(temp_path):
                            with open(temp_path, "r") as f:
                                return int(f.read().strip()) / 1000.0
        except Exception:
            pass
        return None

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        overall_pct = 0.0
        core_pcts: List[float] = []

        try:
            with open("/proc/stat", "r") as f:
                lines = f.readlines()

            new_core_times = []
            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "cpu":
                    values = [int(x) for x in parts[1:8]]
                    idle = values[3] + values[4]
                    total = sum(values)
                    delta_total = total - self._prev_total_time
                    delta_idle = idle - self._prev_idle_time
                    if delta_total > 0:
                        overall_pct = max(0.0, min(100.0, (1.0 - (delta_idle / delta_total)) * 100.0))
                    self._prev_total_time = total
                    self._prev_idle_time = idle
                elif parts[0].startswith("cpu") and parts[0][3:].isdigit():
                    core_idx = int(parts[0][3:])
                    values = [int(x) for x in parts[1:8]]
                    idle = values[3] + values[4]
                    total = sum(values)
                    new_core_times.append((idle, total))
                    
                    if core_idx < len(self._prev_core_times):
                        p_idle, p_total = self._prev_core_times[core_idx]
                        d_total = total - p_total
                        d_idle = idle - p_idle
                        cpct = max(0.0, min(100.0, (1.0 - (d_idle / d_total)) * 100.0)) if d_total > 0 else 0.0
                    else:
                        cpct = 0.0
                    core_pcts.append(cpct)

            self._prev_core_times = new_core_times
            self.overall_history.append(overall_pct)

            # Ensure core histories length matches
            while len(self.core_histories) < len(core_pcts):
                self.core_histories.append(RingBuffer(self.history_len, 0.0))
            for i, cpct in enumerate(core_pcts):
                self.core_histories[i].append(cpct)

        except Exception as e:
            self.error = f"Error reading /proc/stat: {e}"

        freqs = self._get_frequencies()
        load1, load5, load15 = self._get_load_averages()
        temp = self._get_cpu_temperature()

        return {
            "model_name": self.model_name,
            "architecture": self.architecture,
            "physical_cores": self.physical_cores,
            "logical_processors": self.logical_processors,
            "overall_percent": overall_pct,
            "overall_history": self.overall_history.as_list(),
            "core_percents": core_pcts,
            "core_histories": [ch.as_list() for ch in self.core_histories],
            "current_frequency_mhz": freqs["current_mhz"],
            "min_frequency_mhz": freqs["min_mhz"],
            "max_frequency_mhz": freqs["max_mhz"],
            "per_core_mhz": freqs["per_core_mhz"],
            "load_1m": load1,
            "load_5m": load5,
            "load_15m": load15,
            "temperature_c": temp,
        }
