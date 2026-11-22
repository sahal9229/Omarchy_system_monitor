"""
Automated unit tests for Process Table sorting, search filtering, and details formatting.
"""
import unittest
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from src.ui.pages.process_page import ProcessPage

class TestProcessTable(unittest.TestCase):
    def setUp(self):
        self.toast_overlay = Adw.ToastOverlay()
        self.page = ProcessPage(self.toast_overlay)
        # Mock process dataset
        self.sample_processes = [
            {
                "pid": 100,
                "ppid": 1,
                "name": "browser",
                "exe_path": "/usr/bin/browser",
                "cmdline": "/usr/bin/browser --no-sandbox",
                "user": "xahal",
                "uid": 1000,
                "cpu_percent": 15.5,
                "memory_bytes": 1024 * 1024 * 500, # 500 MiB
                "memory_percent": 3.1,
                "state": "Running",
                "runtime_sec": 3665 # 1h 1m 5s
            },
            {
                "pid": 50,
                "ppid": 1,
                "name": "systemd",
                "exe_path": "/usr/lib/systemd/systemd",
                "cmdline": "/usr/lib/systemd/systemd --user",
                "user": "xahal",
                "uid": 1000,
                "cpu_percent": 0.2,
                "memory_bytes": 1024 * 1024 * 25, # 25 MiB
                "memory_percent": 0.2,
                "state": "Sleeping",
                "runtime_sec": 12000
            },
            {
                "pid": 200,
                "ppid": 1,
                "name": "heavy_compiler",
                "exe_path": "/usr/bin/gcc",
                "cmdline": "gcc -O3 main.c",
                "user": "xahal",
                "uid": 1000,
                "cpu_percent": 88.0,
                "memory_bytes": 1024 * 1024 * 1500, # 1.46 GiB
                "memory_percent": 9.5,
                "state": "Running",
                "runtime_sec": 45
            },
            {
                "pid": 120,
                "ppid": 100,
                "name": "browser_tab",
                "exe_path": "/usr/bin/browser",
                "cmdline": "/usr/bin/browser --type=renderer",
                "user": "xahal",
                "uid": 1000,
                "cpu_percent": 5.0,
                "memory_bytes": 1024 * 1024 * 350, # 350 MiB
                "memory_percent": 2.2,
                "state": "Sleeping",
                "runtime_sec": 200
            }
        ]
        self.page.raw_processes = list(self.sample_processes)

    def test_default_cpu_sorting(self):
        # Default sort should be CPU% descending
        self.page.sort_key = "cpu_percent"
        self.page.sort_descending = True
        self.page._filter_and_sort()

        pids = [p["pid"] for p in self.page.filtered_processes]
        # Expect heavy_compiler (88%), browser (15.5%), browser_tab (5%), systemd (0.2%)
        self.assertEqual(pids, [200, 100, 120, 50])

    def test_cpu_sorting_reverse(self):
        # Reverse to ascending (lowest first)
        self.page.sort_key = "cpu_percent"
        self.page.sort_descending = False
        self.page._filter_and_sort()

        pids = [p["pid"] for p in self.page.filtered_processes]
        self.assertEqual(pids, [50, 120, 100, 200])

    def test_memory_sorting(self):
        # Memory descending (highest RAM first)
        self.page.sort_key = "memory_bytes"
        self.page.sort_descending = True
        self.page._filter_and_sort()

        pids = [p["pid"] for p in self.page.filtered_processes]
        # 1500 MiB (200), 500 MiB (100), 350 MiB (120), 25 MiB (50)
        self.assertEqual(pids, [200, 100, 120, 50])

    def test_name_and_pid_sorting(self):
        # Name ascending
        self.page.sort_key = "name"
        self.page.sort_descending = False
        self.page._filter_and_sort()
        names = [p["name"] for p in self.page.filtered_processes]
        self.assertEqual(names, ["browser", "browser_tab", "heavy_compiler", "systemd"])

        # PID ascending
        self.page.sort_key = "pid"
        self.page.sort_descending = False
        self.page._filter_and_sort()
        pids = [p["pid"] for p in self.page.filtered_processes]
        self.assertEqual(pids, [50, 100, 120, 200])

    def test_search_and_sorting_synergy(self):
        # Filter for "browser"
        self.page.search_entry.set_text("browser")
        self.page.sort_key = "cpu_percent"
        self.page.sort_descending = True
        self.page._filter_and_sort()

        # Should match only "browser" and "browser_tab"
        self.assertEqual(len(self.page.filtered_processes), 2)
        # Highest CPU first: browser (15.5%) then browser_tab (5.0%)
        self.assertEqual(self.page.filtered_processes[0]["pid"], 100)
        self.assertEqual(self.page.filtered_processes[1]["pid"], 120)

        # Now sort by memory ascending
        self.page.sort_key = "memory_bytes"
        self.page.sort_descending = False
        self.page._filter_and_sort()
        # 350 MiB (120) then 500 MiB (100)
        self.assertEqual(self.page.filtered_processes[0]["pid"], 120)
        self.assertEqual(self.page.filtered_processes[1]["pid"], 100)

    def test_details_formatting(self):
        proc = self.sample_processes[0]
        self.page._update_details_panel(proc)
        self.assertEqual(self.page.d_stat_name["value"].get_label(), "browser")
        self.assertEqual(self.page.d_stat_pid["value"].get_label(), "100 (PPID: 1)")
        self.assertEqual(self.page.d_stat_runtime["value"].get_label(), "1h 1m 5s")
        self.assertEqual(self.page.d_stat_exe["value"].get_label(), "/usr/bin/browser")
        self.assertEqual(self.page.d_cmdline.get_label(), "/usr/bin/browser --no-sandbox")

    def test_responsive_layout_modes(self):
        self.page.set_responsive_layout(1250)
        self.assertEqual(self.page.layout_mode, "wide")
        self.assertTrue(self.page.btn_col_user.get_visible())
        self.assertTrue(self.page.btn_col_status.get_visible())

        self.page.set_responsive_layout(950)
        self.assertEqual(self.page.layout_mode, "medium")
        self.assertTrue(self.page.btn_col_user.get_visible())

        self.page.set_responsive_layout(700)
        self.assertEqual(self.page.layout_mode, "compact")
        # In compact mode, User and Status columns are hidden to avoid clipping
        self.assertFalse(self.page.btn_col_user.get_visible())
        self.assertFalse(self.page.btn_col_status.get_visible())

if __name__ == "__main__":
    unittest.main()
