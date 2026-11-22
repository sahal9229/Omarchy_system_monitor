"""
Disk and filesystem metrics collector.
Parses /proc/diskstats and queries filesystem mount points via os.statvfs.
Distinguishes physical block device I/O from logical filesystem capacity.

Optimized with:
- Decoupled sampling: fast 1s block I/O throughput vs throttled (5s) static mount/statvfs scanning
- Cached NVMe temperature reading (5s throttle) to prevent NVMe PCIe low-power state wakeups
- Pre-discovered primary block device
"""
import os
import time
from typing import Dict, List, Optional, Tuple
from .base import BaseCollector, RingBuffer

class DiskCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("disk")
        self.history_len = history_len
        self.read_speed_history = RingBuffer(history_len, 0.0)
        self.write_speed_history = RingBuffer(history_len, 0.0)
        
        # Track previous sector counts: device -> (read_sectors, write_sectors, timestamp)
        self._prev_stats: Dict[str, Tuple[int, int, float]] = {}
        self.primary_device: Optional[str] = None
        
        # Throttled filesystem cache
        self._cached_filesystems: List[dict] = []
        self._last_fs_check: float = 0.0
        
        # Throttled NVMe temp cache
        self._nvme_temp_path: Optional[str] = None
        self._cached_ssd_temp: Optional[float] = None
        self._last_temp_check: float = 0.0
        
        self._find_primary_device()
        self._find_nvme_temp_path()
        self._prime_diskstats()

    def _find_primary_device(self):
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

    def _find_nvme_temp_path(self):
        hwmon_root = "/sys/class/hwmon"
        if not os.path.exists(hwmon_root):
            return
        try:
            for h in os.listdir(hwmon_root):
                name_path = os.path.join(hwmon_root, h, "name")
                if os.path.exists(name_path):
                    with open(name_path, "r") as f:
                        if f.read().strip() == "nvme":
                            temp_path = os.path.join(hwmon_root, h, "temp1_input")
                            if os.path.exists(temp_path):
                                self._nvme_temp_path = temp_path
                                return
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
                        r_sect = int(parts[5])
                        w_sect = int(parts[9])
                        self._prev_stats[dev] = (r_sect, w_sect, now)
        except Exception as e:
            self.error = f"Failed to prime /proc/diskstats: {e}"

    def _get_filesystems(self) -> List[dict]:
        now = time.time()
        # Return cached list if polled within last 5 seconds
        if self._cached_filesystems and (now - self._last_fs_check < 5.0):
            return self._cached_filesystems

        self._last_fs_check = now
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
                        if mount.startswith(("/proc", "/sys", "/dev")):
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

        self._cached_filesystems = fs_list
        return fs_list

    def _get_ssd_temperature(self) -> Optional[float]:
        if not self._nvme_temp_path:
            return None
        now = time.time()
        if self._cached_ssd_temp is not None and (now - self._last_temp_check < 5.0):
            return self._cached_ssd_temp

        self._last_temp_check = now
        try:
            with open(self._nvme_temp_path, "r") as f:
                self._cached_ssd_temp = int(f.read().strip()) / 1000.0
                return self._cached_ssd_temp
        except Exception:
            return self._cached_ssd_temp

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        read_bytes_sec = 0.0
        write_bytes_sec = 0.0
        SECTOR_SIZE = 512

        try:
            with open("/proc/diskstats", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 14:
                        dev = parts[2]
                        if self.primary_device and dev != self.primary_device:
                            continue

                        r_sect = int(parts[5])
                        w_sect = int(parts[9])

                        if dev in self._prev_stats:
                            prev_r, prev_w, prev_t = self._prev_stats[dev]
                            dt = now - prev_t
                            if dt > 0:
                                d_read_bytes = (r_sect - prev_r) * SECTOR_SIZE
                                d_write_bytes = (w_sect - prev_w) * SECTOR_SIZE
                                read_bytes_sec += max(0.0, d_read_bytes / dt)
                                write_bytes_sec += max(0.0, d_write_bytes / dt)

                        self._prev_stats[dev] = (r_sect, w_sect, now)
        except Exception as e:
            self.error = f"Error reading /proc/diskstats: {e}"

        self.read_speed_history.append(read_bytes_sec)
        self.write_speed_history.append(write_bytes_sec)

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
            "read_speed_bps": read_bytes_sec,
            "write_speed_bps": write_bytes_sec,
            "read_bytes_sec": read_bytes_sec,
            "write_bytes_sec": write_bytes_sec,
            "read_history": self.read_speed_history.as_list(),
            "write_history": self.write_speed_history.as_list(),
            "filesystems": filesystems,
            "temperature_c": ssd_temp,
            "ssd_temperature_c": ssd_temp,
            "device_rates": {self.primary_device or "disk": {"read_bps": read_bytes_sec, "write_bps": write_bytes_sec}},
        }
