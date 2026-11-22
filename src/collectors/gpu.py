"""
GPU metrics collector.
Supports Intel integrated graphics, AMD Radeon, and NVIDIA GPUs.
Modular vendor-based detection.
"""
import os
import glob
import time
import subprocess
from typing import Dict, List, Optional
from .base import BaseCollector, RingBuffer

class GPUCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("gpu")
        self.history_len = history_len
        self.usage_history = RingBuffer(history_len, 0.0)
        self.vendor = "Unknown"
        self.name = "Unknown GPU"
        self.drm_card = None
        self._detect_gpu()

    def _detect_gpu(self):
        # Scan /sys/class/drm/card*
        for card_path in sorted(glob.glob("/sys/class/drm/card[0-9]")):
            device_path = os.path.join(card_path, "device")
            if not os.path.exists(device_path):
                continue
            
            # Check vendor
            vendor_file = os.path.join(device_path, "vendor")
            if os.path.exists(vendor_file):
                try:
                    with open(vendor_file, "r") as f:
                        v_id = f.read().strip().lower()
                    if v_id == "0x8086":
                        self.vendor = "Intel"
                        self.drm_card = card_path
                        self.name = self._get_device_name_lspci("0000:00:02.0") or "Intel Integrated Graphics"
                        return
                    elif v_id == "0x1002":
                        self.vendor = "AMD"
                        self.drm_card = card_path
                        self.name = "AMD Radeon Graphics"
                        return
                    elif v_id == "0x10de":
                        self.vendor = "NVIDIA"
                        self.drm_card = card_path
                        self.name = "NVIDIA Graphics Device"
                        return
                except Exception:
                    pass

        # Fallback to lspci
        try:
            out = subprocess.check_output(["lspci"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if any(x in line for x in ["VGA compatible controller", "3D controller", "Display controller"]):
                    if "Intel" in line:
                        self.vendor = "Intel"
                        self.name = line.split(":", 2)[-1].strip()
                        # Find matching card in /sys/class/drm/
                        cards = sorted(glob.glob("/sys/class/drm/card[0-9]"))
                        if cards:
                            self.drm_card = cards[0]
                        return
                    elif "AMD" in line or "Advanced Micro Devices" in line:
                        self.vendor = "AMD"
                        self.name = line.split(":", 2)[-1].strip()
                        return
                    elif "NVIDIA" in line:
                        self.vendor = "NVIDIA"
                        self.name = line.split(":", 2)[-1].strip()
                        return
        except Exception:
            pass

    def _get_device_name_lspci(self, pci_addr: str) -> Optional[str]:
        try:
            out = subprocess.check_output(["lspci", "-s", pci_addr], text=True, stderr=subprocess.DEVNULL)
            parts = out.strip().split(":", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        except Exception:
            pass
        return None

    def _read_sysfs_int(self, path: str) -> Optional[int]:
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return int(f.read().strip())
        except Exception:
            pass
        return None

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        usage_pct: Optional[float] = None
        current_freq_mhz: Optional[float] = None
        min_freq_mhz: Optional[float] = None
        max_freq_mhz: Optional[float] = None
        temperature_c: Optional[float] = None
        power_w: Optional[float] = None
        memory_used_bytes: Optional[int] = None
        memory_total_bytes: Optional[int] = None
        memory_type: str = "Dedicated"

        if self.vendor == "Intel" and self.drm_card:
            # Frequency info from sysfs
            act_freq = self._read_sysfs_int(os.path.join(self.drm_card, "gt_act_freq_mhz"))
            cur_freq = self._read_sysfs_int(os.path.join(self.drm_card, "gt_cur_freq_mhz"))
            min_freq = self._read_sysfs_int(os.path.join(self.drm_card, "gt_min_freq_mhz"))
            max_freq = self._read_sysfs_int(os.path.join(self.drm_card, "gt_max_freq_mhz"))

            current_freq_mhz = act_freq if act_freq is not None else cur_freq
            min_freq_mhz = float(min_freq) if min_freq is not None else None
            max_freq_mhz = float(max_freq) if max_freq is not None else None

            # Calculate approximate activity percentage based on frequency scaling
            # between min and max frequency
            if current_freq_mhz is not None and min_freq_mhz is not None and max_freq_mhz is not None:
                span = max_freq_mhz - min_freq_mhz
                if span > 0:
                    usage_pct = max(0.0, min(100.0, ((current_freq_mhz - min_freq_mhz) / span) * 100.0))
                else:
                    usage_pct = 0.0

            memory_type = "Unified System Memory"

        elif self.vendor == "AMD" and self.drm_card:
            dev_path = os.path.join(self.drm_card, "device")
            busy = self._read_sysfs_int(os.path.join(dev_path, "gpu_busy_percent"))
            if busy is not None:
                usage_pct = float(busy)
            
            vram_used = self._read_sysfs_int(os.path.join(dev_path, "mem_info_vram_used"))
            vram_total = self._read_sysfs_int(os.path.join(dev_path, "mem_info_vram_total"))
            if vram_used is not None:
                memory_used_bytes = vram_used
            if vram_total is not None:
                memory_total_bytes = vram_total

        elif self.vendor == "NVIDIA":
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,power.draw,memory.used,memory.total,clocks.current.graphics", "--format=csv,noheader,nounits"],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
                parts = [p.strip() for p in out.split(",")]
                if len(parts) >= 6:
                    usage_pct = float(parts[0])
                    temperature_c = float(parts[1])
                    power_w = float(parts[2])
                    memory_used_bytes = int(parts[3]) * 1024 * 1024
                    memory_total_bytes = int(parts[4]) * 1024 * 1024
                    current_freq_mhz = float(parts[5])
            except Exception:
                pass

        if usage_pct is not None:
            self.usage_history.append(usage_pct)
        else:
            self.usage_history.append(0.0)

        return {
            "vendor": self.vendor,
            "name": self.name,
            "usage_percent": usage_pct,
            "usage_history": self.usage_history.as_list(),
            "current_frequency_mhz": current_freq_mhz,
            "min_frequency_mhz": min_freq_mhz,
            "max_frequency_mhz": max_freq_mhz,
            "temperature_c": temperature_c,
            "power_w": power_w,
            "memory_type": memory_type,
            "memory_used_bytes": memory_used_bytes,
            "memory_total_bytes": memory_total_bytes,
        }
