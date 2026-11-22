"""
Process manager and metrics collector.
Parses /proc/[0-9]+/ to inspect running processes, calculate CPU and memory usage,
and provides safe, confirmation-based process termination.

Optimized with:
- Static metadata caching per PID+starttime (comm, user, uid, ppid, exe, cmdline)
- Fast /proc/[pid]/stat extraction (RSS page extraction directly from field 24)
- Zero status/cmdline/exe file re-reads for established processes
- Fast path parsing with minimal object allocation
"""
import os
import pwd
import time
import signal
from typing import Dict, List, Optional, Tuple
from .base import BaseCollector

class ProcessCollector(BaseCollector):
    def __init__(self):
        super().__init__("process")
        self._user_cache: Dict[int, str] = {}
        # PID -> (utime + stime, timestamp)
        self._prev_proc_times: Dict[int, Tuple[float, float]] = {}
        # PID -> (starttime, name, user, uid, ppid, exe_path, cmdline)
        self._proc_meta_cache: Dict[int, Tuple[int, str, str, int, int, str, str]] = {}
        
        self._clk_tck = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", "SC_CLK_TCK")) or 100
        self._page_size = os.sysconf(os.sysconf_names.get("SC_PAGE_SIZE", "SC_PAGE_SIZE")) or 4096
        self._total_memory = self._get_total_memory()
        
        self._state_map = {
            "R": "Running",
            "S": "Sleeping",
            "D": "Disk Sleep",
            "Z": "Zombie",
            "T": "Stopped",
            "t": "Tracing Stop",
            "X": "Dead",
            "I": "Idle"
        }

    def _get_total_memory(self) -> int:
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
        except Exception:
            pass
        return 1

    def _get_username(self, uid: int) -> str:
        if uid in self._user_cache:
            return self._user_cache[uid]
        try:
            name = pwd.getpwuid(uid).pw_name
        except Exception:
            name = str(uid)
        self._user_cache[uid] = name
        return name

    def _get_system_uptime(self) -> float:
        try:
            with open("/proc/uptime", "r") as f:
                return float(f.read().split()[0])
        except Exception:
            return time.time()

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now
        uptime = self._get_system_uptime()

        processes: List[dict] = []
        new_proc_times: Dict[int, Tuple[float, float]] = {}
        new_meta_cache: Dict[int, Tuple[int, str, str, int, int, str, str]] = {}

        clk_tck = float(self._clk_tck)
        page_size = self._page_size
        total_mem = float(self._total_memory) if self._total_memory > 0 else 1.0
        state_map = self._state_map
        prev_times = self._prev_proc_times
        meta_cache = self._proc_meta_cache

        # Scan numeric entries in /proc
        try:
            entries = os.listdir("/proc")
        except Exception as e:
            self.error = f"Failed to list /proc: {e}"
            return {"processes": [], "total_count": 0}

        for entry in entries:
            if not entry.isdigit():
                continue
            pid = int(entry)
            proc_dir = f"/proc/{entry}"

            try:
                # Read /proc/[pid]/stat
                with open(f"{proc_dir}/stat", "r", encoding="utf-8", errors="replace") as f:
                    stat_content = f.read()

                l_paren = stat_content.find("(")
                r_paren = stat_content.rfind(")")
                if l_paren == -1 or r_paren == -1:
                    continue

                comm = stat_content[l_paren + 1:r_paren]
                rest = stat_content[r_paren + 2:].split()

                state_code = rest[0]
                ppid = int(rest[1])
                utime = int(rest[11])
                stime = int(rest[12])
                starttime = int(rest[19])
                # Field 24 in stat (rest[21]): RSS in pages
                rss_pages = int(rest[21])
                rss_bytes = max(0, rss_pages * page_size)

                total_proc_time = (utime + stime) / clk_tck
                new_proc_times[pid] = (total_proc_time, now)

                # CPU percentage calculation
                cpu_pct = 0.0
                if pid in prev_times:
                    prev_t, prev_stamp = prev_times[pid]
                    dt = now - prev_stamp
                    if dt > 0:
                        delta_proc = total_proc_time - prev_t
                        if delta_proc > 0:
                            cpu_pct = max(0.0, (delta_proc / dt) * 100.0)

                # Static metadata: use cache if PID and starttime match
                cached = meta_cache.get(pid)
                if cached and cached[0] == starttime:
                    _, name, user, uid, ppid, exe_path, cmdline = cached
                else:
                    # New or recycled PID: discover static attributes
                    # 1. UID via stat() of the proc dir without opening /proc/pid/status
                    try:
                        uid = os.stat(proc_dir).st_uid
                    except Exception:
                        uid = 0
                    user = self._get_username(uid)

                    # 2. Executable path
                    exe_path = ""
                    try:
                        exe_path = os.readlink(f"{proc_dir}/exe")
                    except Exception:
                        exe_path = ""

                    # 3. Command line
                    cmdline = comm
                    try:
                        with open(f"{proc_dir}/cmdline", "r", encoding="utf-8", errors="replace") as f:
                            raw_cmd = f.read().replace("\x00", " ").strip()
                            if raw_cmd:
                                cmdline = raw_cmd
                    except Exception:
                        pass

                    name = comm
                    if not exe_path and cmdline:
                        exe_path = cmdline.split()[0]
                    elif not exe_path:
                        exe_path = comm

                new_meta_cache[pid] = (starttime, name, user, uid, ppid, exe_path, cmdline)

                mem_pct = (rss_bytes / total_mem) * 100.0
                process_runtime_sec = max(0.0, uptime - (starttime / clk_tck))

                processes.append({
                    "pid": pid,
                    "ppid": ppid,
                    "name": name,
                    "exe_path": exe_path,
                    "cmdline": cmdline,
                    "user": user,
                    "uid": uid,
                    "cpu_percent": round(cpu_pct, 1),
                    "memory_bytes": rss_bytes,
                    "memory_percent": round(mem_pct, 1),
                    "state": state_map.get(state_code, state_code),
                    "runtime_sec": int(process_runtime_sec),
                })

            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            except Exception:
                continue

        self._prev_proc_times = new_proc_times
        self._proc_meta_cache = new_meta_cache

        return {
            "processes": processes,
            "total_count": len(processes),
        }

    @staticmethod
    def terminate_process(pid: int, sig: signal.Signals = signal.SIGTERM) -> Tuple[bool, str]:
        """Safely terminate a user-owned process with clear error messages."""
        if pid <= 1:
            return False, f"Refusing to terminate system-critical PID {pid}."

        current_uid = os.getuid()
        try:
            # Check ownership via stat
            proc_uid = os.stat(f"/proc/{pid}").st_uid
            
            if current_uid != 0 and proc_uid != current_uid:
                return False, f"Cannot terminate PID {pid}: owned by user ID {proc_uid} (insufficient permissions)."

            os.kill(pid, sig)
            return True, f"Signal {sig.name} successfully delivered to PID {pid}."

        except ProcessLookupError:
            return False, f"Process {pid} no longer exists."
        except PermissionError:
            return False, f"Permission denied terminating process {pid}."
        except Exception as e:
            return False, f"Failed to terminate process {pid}: {e}"
