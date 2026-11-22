"""
Process manager and metrics collector.
Parses /proc/[0-9]+/ to inspect running processes, calculate CPU and memory usage,
and provides safe, confirmation-based process termination.
"""
import os
import pwd
import time
import signal
from typing import Dict, List, Optional
from .base import BaseCollector

class ProcessCollector(BaseCollector):
    def __init__(self):
        super().__init__("process")
        self._user_cache: Dict[int, str] = {}
        # PID -> (utime + stime, timestamp)
        self._prev_proc_times: Dict[int, tuple] = {}
        self._clk_tck = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", "SC_CLK_TCK")) or 100
        self._total_memory = self._get_total_memory()

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
        new_proc_times: Dict[int, tuple] = {}

        # Scan numeric entries in /proc
        try:
            pids = [int(p) for p in os.listdir("/proc") if p.isdigit()]
        except Exception as e:
            self.error = f"Failed to list /proc: {e}"
            return {"processes": []}

        for pid in pids:
            proc_dir = f"/proc/{pid}"
            try:
                # Read /proc/[pid]/stat
                # Format: pid (comm) state ppid pgrp session tty_nr tpgid flags minflt cminflt majflt cmajflt utime stime cutime cstime priority nice num_threads itrealvalue starttime ...
                with open(f"{proc_dir}/stat", "r", encoding="utf-8", errors="replace") as f:
                    stat_content = f.read()

                # Process name is enclosed in parentheses
                l_paren = stat_content.find("(")
                r_paren = stat_content.rfind(")")
                if l_paren == -1 or r_paren == -1:
                    continue

                comm = stat_content[l_paren + 1:r_paren]
                rest = stat_content[r_paren + 2:].split()

                state = rest[0]
                ppid = int(rest[1])
                utime = int(rest[11])
                stime = int(rest[12])
                starttime = int(rest[19])

                total_proc_time = (utime + stime) / float(self._clk_tck)
                new_proc_times[pid] = (total_proc_time, now)

                # CPU percentage calculation
                cpu_pct = 0.0
                if pid in self._prev_proc_times:
                    prev_t, prev_stamp = self._prev_proc_times[pid]
                    dt = now - prev_stamp
                    if dt > 0:
                        delta_proc = total_proc_time - prev_t
                        if delta_proc > 0:
                            # Percentage across cores
                            cpu_pct = max(0.0, (delta_proc / dt) * 100.0)

                # Read UID from /proc/[pid]/status
                uid = 0
                rss_bytes = 0
                try:
                    with open(f"{proc_dir}/status", "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            if line.startswith("Uid:"):
                                uid = int(line.split()[1])
                            elif line.startswith("VmRSS:"):
                                # in kB
                                rss_bytes = int(line.split()[1]) * 1024
                except Exception:
                    pass

                user = self._get_username(uid)
                mem_pct = (rss_bytes / self._total_memory * 100.0) if self._total_memory > 0 else 0.0

                # Runtime in seconds
                process_runtime_sec = max(0.0, uptime - (starttime / float(self._clk_tck)))

                # Executable path and command line
                cmdline = comm
                exe_path = ""
                try:
                    exe_path = os.readlink(f"{proc_dir}/exe")
                except Exception:
                    exe_path = ""

                try:
                    with open(f"{proc_dir}/cmdline", "r", encoding="utf-8", errors="replace") as f:
                        raw_cmd = f.read().replace("\x00", " ").strip()
                        if raw_cmd:
                            cmdline = raw_cmd
                except Exception:
                    pass

                state_map = {
                    "R": "Running",
                    "S": "Sleeping",
                    "D": "Disk Sleep",
                    "Z": "Zombie",
                    "T": "Stopped",
                    "t": "Tracing Stop",
                    "X": "Dead",
                    "I": "Idle"
                }

                processes.append({
                    "pid": pid,
                    "ppid": ppid,
                    "name": comm,
                    "exe_path": exe_path or cmdline.split()[0] if cmdline else comm,
                    "cmdline": cmdline,
                    "user": user,
                    "uid": uid,
                    "cpu_percent": round(cpu_pct, 1),
                    "memory_bytes": rss_bytes,
                    "memory_percent": round(mem_pct, 1),
                    "state": state_map.get(state, state),
                    "runtime_sec": int(process_runtime_sec),
                })

            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            except Exception:
                continue

        self._prev_proc_times = new_proc_times

        # Clean up old pids from prev_proc_times
        active_pids = set(new_proc_times.keys())
        self._prev_proc_times = {k: v for k, v in self._prev_proc_times.items() if k in active_pids}

        return {
            "processes": processes,
            "total_count": len(processes),
        }

    @staticmethod
    def terminate_process(pid: int, sig: signal.Signals = signal.SIGTERM) -> tuple[bool, str]:
        """Safely terminate a user-owned process with clear error messages."""
        if pid <= 1:
            return False, f"Refusing to terminate system-critical PID {pid}."

        current_uid = os.getuid()
        try:
            # Check ownership
            with open(f"/proc/{pid}/status", "r") as f:
                proc_uid = None
                for line in f:
                    if line.startswith("Uid:"):
                        proc_uid = int(line.split()[1])
                        break
            
            if current_uid != 0 and proc_uid is not None and proc_uid != current_uid:
                return False, f"Cannot terminate PID {pid}: owned by user ID {proc_uid} (insufficient permissions)."

            os.kill(pid, sig)
            return True, f"Signal {sig.name} successfully delivered to PID {pid}."

        except ProcessLookupError:
            return False, f"Process {pid} no longer exists."
        except PermissionError:
            return False, f"Permission denied terminating process {pid}."
        except Exception as e:
            return False, f"Failed to terminate process {pid}: {e}"
