"""
Automated unit tests for system metric collectors.
"""
import unittest
import time
import os
import signal
from src.collectors.base import RingBuffer
from src.collectors.cpu import CPUCollector
from src.collectors.memory import MemoryCollector
from src.collectors.gpu import GPUCollector
from src.collectors.disk import DiskCollector
from src.collectors.network import NetworkCollector
from src.collectors.battery import BatteryCollector
from src.collectors.sensors import SensorsCollector
from src.collectors.process import ProcessCollector

class TestCollectors(unittest.TestCase):
    def test_ring_buffer(self):
        rb = RingBuffer(maxlen=5, default_value=0.0)
        self.assertEqual(len(rb), 5)
        self.assertEqual(rb.as_list(), [0.0, 0.0, 0.0, 0.0, 0.0])
        rb.append(10.0)
        self.assertEqual(rb.as_list(), [0.0, 0.0, 0.0, 0.0, 10.0])
        self.assertEqual(rb.last(), 10.0)
        self.assertEqual(rb.min_max(), (0.0, 10.0))

    def test_cpu_collector(self):
        collector = CPUCollector(history_len=10)
        self.assertIsNotNone(collector.model_name)
        self.assertGreaterEqual(collector.logical_processors, 1)
        self.assertGreaterEqual(collector.physical_cores, 1)
        
        # Give a small tick for delta calculation
        time.sleep(0.1)
        metrics = collector.update()
        self.assertIn("overall_percent", metrics)
        self.assertGreaterEqual(metrics["overall_percent"], 0.0)
        self.assertLessEqual(metrics["overall_percent"], 100.0)
        self.assertEqual(len(metrics["core_percents"]), collector.logical_processors)
        self.assertIn("load_1m", metrics)

    def test_memory_collector(self):
        collector = MemoryCollector(history_len=10)
        metrics = collector.update()
        self.assertIn("total_ram", metrics)
        self.assertGreater(metrics["total_ram"], 0)
        self.assertIn("used_ram", metrics)
        self.assertIn("available_ram", metrics)
        self.assertGreaterEqual(metrics["ram_percent"], 0.0)
        self.assertLessEqual(metrics["ram_percent"], 100.0)
        self.assertIn("swap_percent", metrics)

    def test_gpu_collector(self):
        collector = GPUCollector(history_len=10)
        metrics = collector.update()
        self.assertIn("vendor", metrics)
        self.assertIn("name", metrics)
        self.assertIn("usage_history", metrics)
        self.assertEqual(len(metrics["usage_history"]), 10)

    def test_disk_collector(self):
        collector = DiskCollector(history_len=10)
        time.sleep(0.05)
        metrics = collector.update()
        self.assertIn("read_speed_bps", metrics)
        self.assertIn("write_speed_bps", metrics)
        self.assertIn("filesystems", metrics)
        self.assertIsInstance(metrics["filesystems"], list)
        if metrics["filesystems"]:
            first_fs = metrics["filesystems"][0]
            self.assertIn("mount_point", first_fs)
            self.assertIn("total_bytes", first_fs)

    def test_network_collector(self):
        collector = NetworkCollector(history_len=10)
        time.sleep(0.05)
        metrics = collector.update()
        self.assertIn("total_rx_bps", metrics)
        self.assertIn("total_tx_bps", metrics)
        self.assertIn("interfaces", metrics)
        self.assertIsInstance(metrics["interfaces"], list)

    def test_battery_collector(self):
        collector = BatteryCollector()
        metrics = collector.update()
        self.assertIn("present", metrics)
        if metrics["present"]:
            self.assertIn("percentage", metrics)
            self.assertIn("status", metrics)

    def test_sensors_collector(self):
        collector = SensorsCollector(history_len=10)
        metrics = collector.update()
        self.assertIn("devices", metrics)
        self.assertIn("primary_cpu_temp_c", metrics)
        self.assertIn("fan_available", metrics)
        # On this Dell laptop, Dell SMM fan should be available
        if metrics["fan_available"]:
            self.assertGreaterEqual(metrics["primary_fan_rpm"], 0)

    def test_process_collector(self):
        collector = ProcessCollector()
        metrics = collector.update()
        self.assertIn("processes", metrics)
        self.assertGreater(metrics["total_count"], 0)
        
        # Test safety on terminate
        success, msg = ProcessCollector.terminate_process(1, signal.SIGTERM)
        self.assertFalse(success)
        self.assertIn("Refusing", msg)

        # Test non-existent PID
        success, msg = ProcessCollector.terminate_process(9999999, signal.SIGTERM)
        self.assertFalse(success)

if __name__ == "__main__":
    unittest.main()
