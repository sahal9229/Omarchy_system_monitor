"""
Network metrics collector.
Parses /proc/net/dev to calculate real-time download (Rx) and upload (Tx) bitrates.
Tracks active network interfaces and bandwidth consumption.

Optimized with:
- Minimal allocations in line parsing
- Cached interface state queries
"""
import os
import time
from typing import Dict, List, Tuple
from .base import BaseCollector, RingBuffer

class NetworkCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("network")
        self.history_len = history_len
        self.rx_speed_history = RingBuffer(history_len, 0.0)
        self.tx_speed_history = RingBuffer(history_len, 0.0)
        
        # Interface -> (rx_bytes, tx_bytes, timestamp)
        self._prev_stats: Dict[str, Tuple[int, int, float]] = {}
        self._state_cache: Dict[str, Tuple[str, float]] = {}
        self._prime_netdev()

    def _prime_netdev(self):
        now = time.time()
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()
            for line in lines[2:]:
                parts = line.split(":")
                if len(parts) == 2:
                    iface = parts[0].strip()
                    metrics = parts[1].split()
                    if len(metrics) >= 9:
                        rx_b = int(metrics[0])
                        tx_b = int(metrics[8])
                        self._prev_stats[iface] = (rx_b, tx_b, now)
        except Exception as e:
            self.error = f"Failed to prime /proc/net/dev: {e}"

    def _get_operstate(self, iface: str, now: float) -> str:
        # Cache interface state for 3 seconds
        cached = self._state_cache.get(iface)
        if cached and (now - cached[1] < 3.0):
            return cached[0]
        
        state_file = f"/sys/class/net/{iface}/operstate"
        state = "unknown"
        try:
            with open(state_file, "r") as f:
                state = f.read().strip()
        except Exception:
            state = "unknown"
        self._state_cache[iface] = (state, now)
        return state

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        total_rx_bps = 0.0
        total_tx_bps = 0.0
        interfaces: List[dict] = []

        try:
            with open("/proc/net/dev", "r") as f:
                for line in f:
                    if ":" not in line:
                        continue
                    parts = line.split(":", 1)
                    iface = parts[0].strip()
                    if iface == "lo":
                        continue

                    metrics = parts[1].split()
                    if len(metrics) < 9:
                        continue

                    rx_bytes = int(metrics[0])
                    tx_bytes = int(metrics[8])

                    rx_bps = 0.0
                    tx_bps = 0.0

                    if iface in self._prev_stats:
                        prev_rx, prev_tx, prev_t = self._prev_stats[iface]
                        dt = now - prev_t
                        if dt > 0:
                            rx_bps = max(0.0, ((rx_bytes - prev_rx) * 8.0) / dt)
                            tx_bps = max(0.0, ((tx_bytes - prev_tx) * 8.0) / dt)
                            total_rx_bps += rx_bps
                            total_tx_bps += tx_bps

                    self._prev_stats[iface] = (rx_bytes, tx_bytes, now)

                    state = self._get_operstate(iface, now)

                    interfaces.append({
                        "name": iface,
                        "state": state,
                        "rx_bps": rx_bps,
                        "tx_bps": tx_bps,
                        "total_rx_bytes": rx_bytes,
                        "total_tx_bytes": tx_bytes,
                    })

        except Exception as e:
            self.error = f"Error reading /proc/net/dev: {e}"

        self.rx_speed_history.append(total_rx_bps)
        self.tx_speed_history.append(total_tx_bps)

        return {
            "total_rx_bps": total_rx_bps,
            "total_tx_bps": total_tx_bps,
            "rx_history": self.rx_speed_history.as_list(),
            "tx_history": self.tx_speed_history.as_list(),
            "interfaces": interfaces,
        }
