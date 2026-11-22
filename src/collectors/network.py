"""
Network performance and interface metrics collector.
Parses /proc/net/dev and /sys/class/net to track download/upload rates and totals.
"""
import os
import time
from typing import Dict, List, Optional
from .base import BaseCollector, RingBuffer

class NetworkCollector(BaseCollector):
    def __init__(self, history_len: int = 60):
        super().__init__("network")
        self.history_len = history_len
        self.rx_speed_history = RingBuffer(history_len, 0.0)
        self.tx_speed_history = RingBuffer(history_len, 0.0)
        
        # Interface -> (rx_bytes, tx_bytes, timestamp)
        self._prev_stats: Dict[str, tuple] = {}
        self._prime_net_dev()

    def _prime_net_dev(self):
        now = time.time()
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()[2:] # Skip header lines
                for line in lines:
                    parts = line.split(":")
                    if len(parts) == 2:
                        iface = parts[0].strip()
                        vals = parts[1].strip().split()
                        rx_bytes = int(vals[0])
                        tx_bytes = int(vals[8])
                        self._prev_stats[iface] = (rx_bytes, tx_bytes, now)
        except Exception as e:
            self.error = f"Failed to prime /proc/net/dev: {e}"

    def _get_interface_type(self, iface: str) -> str:
        if iface.startswith("wl") or iface.startswith("wlan"):
            return "Wi-Fi"
        elif iface.startswith("en") or iface.startswith("eth"):
            return "Ethernet"
        elif iface == "lo":
            return "Loopback"
        elif iface.startswith("tun") or iface.startswith("wg") or iface.startswith("tap"):
            return "VPN / Tunnel"
        return "Network Interface"

    def _get_interface_status(self, iface: str) -> str:
        state_file = f"/sys/class/net/{iface}/operstate"
        try:
            if os.path.exists(state_file):
                with open(state_file, "r") as f:
                    return f.read().strip()
        except Exception:
            pass
        return "unknown"

    def update(self) -> dict:
        now = time.time()
        self.last_update_time = now

        total_rx_bps = 0.0
        total_tx_bps = 0.0
        interfaces = []

        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()[2:]

            for line in lines:
                parts = line.split(":")
                if len(parts) != 2:
                    continue
                iface = parts[0].strip()
                vals = parts[1].strip().split()
                rx_bytes = int(vals[0])
                rx_packets = int(vals[1])
                tx_bytes = int(vals[8])
                tx_packets = int(vals[9])

                rx_rate = 0.0
                tx_rate = 0.0

                if iface in self._prev_stats:
                    prev_rx, prev_tx, prev_t = self._prev_stats[iface]
                    dt = now - prev_t
                    if dt > 0:
                        rx_rate = max(0.0, (rx_bytes - prev_rx) / dt)
                        tx_rate = max(0.0, (tx_bytes - prev_tx) / dt)

                self._prev_stats[iface] = (rx_bytes, tx_bytes, now)

                # Ignore loopback for aggregated speed
                if iface != "lo":
                    total_rx_bps += rx_rate
                    total_tx_bps += tx_rate

                operstate = self._get_interface_status(iface)
                iface_type = self._get_interface_type(iface)

                interfaces.append({
                    "name": iface,
                    "type": iface_type,
                    "status": operstate,
                    "rx_speed_bps": rx_rate,
                    "tx_speed_bps": tx_rate,
                    "total_rx_bytes": rx_bytes,
                    "total_tx_bytes": tx_bytes,
                    "rx_packets": rx_packets,
                    "tx_packets": tx_packets,
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
