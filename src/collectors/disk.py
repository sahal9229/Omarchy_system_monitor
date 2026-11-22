"""
Disk and filesystem metrics collector.
Parses /proc/diskstats and queries filesystem mount points via os.statvfs.
Distinguishes physical block device I/O from logical filesystem capacity.
"""
import os
import time
from typing import Dict, List, Optional
from .base import BaseCollector, RingBuffer

class DiskCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("disk")
        self.history_len = history_len
        self.read_speed_history = RingBuffer(history_len, 0.0)
        self.write_speed_history = RingBuffer(history_len, 0.0)
        
        # Track previous sector counts: device -> (read_sectors, write_sectors, timestamp)
        self._prev_stats: Dict[str, tuple] = {}
        self.primary_device: Optional[str] = None
        self._find_primary_device()
        self._prime_diskstats()

    def _find_primary_device(self):
        # Look for physical root disk e.g. nvme0n1 or sda
        try:
            with open("/proc/diskstats", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 14:
                        dev = parts[2]
                        if dev.startswith("nvme") and "p" not in dev:
                            self.primary_device = dev
                            return
                        elif (dev.startswith("sd") or dev.startswith("vd")) and not dev[-1].isdigit():
                            if not self.primary_device:
                                self.primary_device = dev
        except Exception:
            pass

    def _prime_diskstats(self):
        now = time.time()
        try:
            with open("/proc/diskstats", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 14:
                        dev = parts[2]
                        # Field 5: sectors read, Field 9: sectors written
                        r_sect = int(parts[5])
                        w_sect = int(parts[9])
                        self._prev_stats[dev] = (r_sect, w_sect, now)
        except Exception as e:
            self.error = f"Failed to prime /proc/diskstats: {e}"

    def _get_filesystems(self) -> List[dict]:
        fs_list = []
        ignored_types = {
            "tmpfs", "devtmpfs", "proc", "sysfs", "securityfs", "cgroup", "cgroup2",
            "pstore", "bpf", "debugfs", "tracefs", "hugetlbfs", "mqueue", "autofs",
            "fusectl", "configfs", "ramfs", "efivarfs"
        }
        seen_mounts = set()
        
        try:
            with open("/proc/mounts", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        dev = parts[0]
                        mount = parts[1]
                        fstype = parts[2]

                        if fstype in ignored_types or mount in seen_mounts:
                            continue
                        if mount.startswith("/proc") or mount.startswith("/sys") or mount.startswith("/dev"):
                            continue
                        
                        try:
                            st = os.statvfs(mount)
                            total = st.f_blocks * st.f_frsize
                            available = st.f_bavail * st.f_frsize
                            free = st.f_bfree * st.f_frsize
                            used = total - free
                            pct = (used / total * 100.0) if total > 0 else 0.0

                            seen_mounts.add(mount)
                            fs_list.append({
                                "device": dev,
                                "mount_point": mount,
                                "filesystem": fstype,
                                "total_bytes": total,
                                "used_bytes": used,
                                "available_bytes": available,
                                "usage_percent": pct,
                            })
                        except Exception:
                            continue
        except Exception:
            pass
        return fs_list

    def _get_ssd_temperature(self) -> Optional[float]:
        try:
            hwmon_root = "/sys/class/hwmon"
            for h in os.listdir(hwmon_root):
                name_path = os.path.join(hwmon_root, h, "name")
                if os.path.exists(name_path):
                    with open(name_path, "r") as f:
                        if f.read().strip() == "nvme":
                            temp_path = os.path.join(hwmon_root, h, "temp1_input")
                            if os.path.exists(temp_path):
                                with open(temp_path, "r") as tf:
                                    return int(tf.read().strip()) / 1000.0
        except Exception:
            pass
        return None

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        total_read_bps = 0.0
        total_write_bps = 0.0
        device_rates: Dict[str, dict] = {}

        try:
            with open("/proc/diskstats", "r") as f:
                lines = f.readlines()

            for line in lines:
                parts = line.split()
                if len(parts) >= 14:
                    dev = parts[2]
                    r_sect = int(parts[5])
                    w_sect = int(parts[9])
                    
                    # Sector size is standard 512 bytes on Linux
                    if dev in self._prev_stats:
                        prev_r, prev_w, prev_t = self._prev_stats[dev]
                        dt = now - prev_t
                        if dt > 0:
                            r_bytes = max(0, (r_sect - prev_r) * 512)
                            w_bytes = max(0, (w_sect - prev_w) * 512)
                            r_rate = r_bytes / dt
                            w_rate = w_bytes / dt

                            # Record physical device rates
                            is_physical = (dev.startswith("nvme") and "p" not in dev) or \
                                          ((dev.startswith("sd") or dev.startswith("vd")) and not dev[-1].isdigit())

                            if is_physical or dev == self.primary_device:
                                total_read_bps += r_rate
                                total_write_bps += w_rate

                            device_rates[dev] = {
                                "read_bps": r_rate,
                                "write_bps": w_rate
                            }

                    self._prev_stats[dev] = (r_sect, w_sect, now)

        except Exception as e:
            self.error = f"Error reading /proc/diskstats: {e}"

        self.read_speed_history.append(total_read_bps)
        self.write_speed_history.append(total_write_bps)

        filesystems = self._get_filesystems()
        ssd_temp = self._get_ssd_temperature()

        # Aggregate total storage
        total_storage = sum(fs["total_bytes"] for fs in filesystems)
        used_storage = sum(fs["used_bytes"] for fs in filesystems)
        storage_pct = (used_storage / total_storage * 100.0) if total_storage > 0 else 0.0

        return {
            "primary_device": self.primary_device or "Unknown",
            "total_storage_bytes": total_storage,
            "used_storage_bytes": used_storage,
            "storage_percent": storage_pct,
            "read_speed_bps": total_read_bps,
            "write_speed_bps": total_write_bps,
            "read_history": self.read_speed_history.as_list(),
            "write_history": self.write_speed_history.as_list(),
            "filesystems": filesystems,
            "ssd_temperature_c": ssd_temp,
            "device_rates": device_rates,
        }
