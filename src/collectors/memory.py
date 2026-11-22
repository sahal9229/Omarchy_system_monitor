"""
Memory and Swap metrics collector.
Parses /proc/meminfo to calculate real memory utilization accurately.
"""
import time
from typing import Dict, Optional
from .base import BaseCollector, RingBuffer

class MemoryCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("memory")
        self.history_len = history_len
        self.ram_history = RingBuffer(history_len, 0.0)
        self.swap_history = RingBuffer(history_len, 0.0)

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        info: Dict[str, int] = {}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        # Values in meminfo are in kB
                        val_str = parts[1].strip().split()[0]
                        info[key] = int(val_str) * 1024 # Convert kB to bytes
        except Exception as e:
            self.error = f"Failed to read /proc/meminfo: {e}"
            return {}

        total_ram = info.get("MemTotal", 0)
        free_ram = info.get("MemFree", 0)
        available_ram = info.get("MemAvailable", 0)
        buffers = info.get("Buffers", 0)
        cached = info.get("Cached", 0)
        sreclaimable = info.get("SReclaimable", 0)
        shmem = info.get("Shmem", 0)

        # Linux kernel calculation for 'used' memory:
        # Used = Total - Available (standard top/htop/free definition)
        used_ram = max(0, total_ram - available_ram)
        ram_pct = (used_ram / total_ram * 100.0) if total_ram > 0 else 0.0

        # Cached memory usually reported as Cached + SReclaimable - Shmem
        buff_cache = buffers + cached + sreclaimable

        total_swap = info.get("SwapTotal", 0)
        free_swap = info.get("SwapFree", 0)
        used_swap = max(0, total_swap - free_swap)
        swap_pct = (used_swap / total_swap * 100.0) if total_swap > 0 else 0.0

        self.ram_history.append(ram_pct)
        self.swap_history.append(swap_pct)

        return {
            "total_ram": total_ram,
            "used_ram": used_ram,
            "available_ram": available_ram,
            "free_ram": free_ram,
            "buffered_ram": buffers,
            "cached_ram": buff_cache,
            "ram_percent": ram_pct,
            "ram_history": self.ram_history.as_list(),
            "total_swap": total_swap,
            "used_swap": used_swap,
            "free_swap": free_swap,
            "swap_percent": swap_pct,
            "swap_history": self.swap_history.as_list(),
        }
