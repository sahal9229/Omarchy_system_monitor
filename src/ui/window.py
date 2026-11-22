"""
Main Application Window with Windows 11 Task Manager style left sidebar navigation.
Houses the view stack, toast overlay, and coordinates the background polling loop.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gdk
import time
import threading

from ..config import ConfigManager
from ..collectors.cpu import CPUCollector
from ..collectors.memory import MemoryCollector
from ..collectors.gpu import GPUCollector
from ..collectors.disk import DiskCollector
from ..collectors.network import NetworkCollector
from ..collectors.battery import BatteryCollector
from ..collectors.sensors import SensorsCollector
from ..collectors.process import ProcessCollector

from .pages.dashboard import DashboardPage
from .pages.cpu_page import CPUPage
from .pages.memory_page import MemoryPage
from .pages.gpu_page import GPUPage
from .pages.disk_page import DiskPage
from .pages.network_page import NetworkPage
from .pages.battery_page import BatteryPage
from .pages.sensors_page import SensorsPage
from .pages.process_page import ProcessPage
from .pages.settings_page import SettingsPage

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app, config_mgr: ConfigManager):
        super().__init__(application=app, title="Omarchy System Monitor")
        self.config_mgr = config_mgr

        self.set_default_size(1040, 700)
        self.set_size_request(420, 360)

        # Polling & Worker Thread
        self._poll_timer_id = None
        self._last_proc_tick = 0.0
        self._running = True
        self._latest_shared_data = {}
        self._wake_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        self.connect("close-request", self._on_close_request)

        # Apply saved theme
        self._apply_theme(self.config_mgr.get("theme", "system"))

        # Initialize Hardware Metric Collectors
        self.cpu_collector = CPUCollector()
        self.mem_collector = MemoryCollector()
        self.gpu_collector = GPUCollector()
        self.disk_collector = DiskCollector()
        self.net_collector = NetworkCollector()
        self.bat_collector = BatteryCollector()
        self.sensors_collector = SensorsCollector()
        self.proc_collector = ProcessCollector()

        # Toast Overlay
        self.toast_overlay = Adw.ToastOverlay()

        # Split View for Sidebar + Content
        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_min_sidebar_width(170)
        self.split_view.set_max_sidebar_width(220)

        # Build Content Stack first
        self.stack = Adw.ViewStack()
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        # Pages
        self.page_dashboard = DashboardPage(self.navigate_to_page, self.config_mgr)
        self.page_processes = ProcessPage(self.toast_overlay)
        self.page_cpu = CPUPage()
        self.page_memory = MemoryPage()
        self.page_gpu = GPUPage()
        self.page_disk = DiskPage()
        self.page_network = NetworkPage()
        self.page_battery = BatteryPage()
        self.page_sensors = SensorsPage(self.config_mgr)
        self.page_settings = SettingsPage(self.config_mgr, self._on_config_changed)

        self.stack.add_titled_with_icon(self.page_dashboard, "dashboard", "Overview", "view-grid-symbolic")
        self.stack.add_titled_with_icon(self.page_processes, "processes", "Processes", "application-x-executable-symbolic")
        self.stack.add_titled_with_icon(self.page_cpu, "cpu", "CPU", "cpu-symbolic")
        self.stack.add_titled_with_icon(self.page_memory, "memory", "Memory", "drive-multidisk-symbolic")
        self.stack.add_titled_with_icon(self.page_gpu, "gpu", "GPU", "video-display-symbolic")
        self.stack.add_titled_with_icon(self.page_disk, "disk", "Disk", "drive-harddisk-symbolic")
        self.stack.add_titled_with_icon(self.page_network, "network", "Network", "network-wireless-symbolic")
        self.stack.add_titled_with_icon(self.page_battery, "battery", "Battery", "battery-symbolic")
        self.stack.add_titled_with_icon(self.page_sensors, "sensors", "Hardware Sensors", "weather-clear-symbolic")
        self.stack.add_titled_with_icon(self.page_settings, "settings", "Settings", "emblem-system-symbolic")

        # Build Sidebar
        sidebar_page = Adw.NavigationPage.new(self._build_sidebar(), "Navigation")
        sidebar_page.set_title("System Monitor")
        self.split_view.set_sidebar(sidebar_page)

        content_page = Adw.NavigationPage.new(self.stack, "Content")
        self.split_view.set_content(content_page)

        # Responsive Breakpoints for Hyprland window tiling
        bp_medium = Adw.Breakpoint.new(Adw.breakpoint_condition_parse("max-width: 1150px"))
        bp_medium.connect("apply", lambda b: self.page_processes.set_responsive_layout(1000))
        bp_medium.connect("unapply", lambda b: self.page_processes.set_responsive_layout(1300))
        self.add_breakpoint(bp_medium)

        bp_compact = Adw.Breakpoint.new(Adw.breakpoint_condition_parse("max-width: 820px"))
        bp_compact.connect("apply", lambda b: self.page_processes.set_responsive_layout(750))
        bp_compact.connect("unapply", lambda b: self.page_processes.set_responsive_layout(1000))
        self.add_breakpoint(bp_compact)

        self.toast_overlay.set_child(self.split_view)
        self.set_content(self.toast_overlay)

        # Start timer and initial tick
        self._setup_timer()
        self._on_poll_tick()

    def _apply_theme(self, theme_str: str):
        style_mgr = Adw.StyleManager.get_default()
        if theme_str == "dark":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif theme_str == "light":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _build_sidebar(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(8)
        box.set_margin_end(8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        header_lbl = Gtk.Label(label="OMARCHY MONITOR")
        header_lbl.set_halign(Gtk.Align.START)
        header_lbl.set_margin_start(12)
        header_lbl.set_margin_bottom(8)
        header_lbl.add_css_class("heading")
        header_lbl.add_css_class("dim-label")
        box.append(header_lbl)

        self.nav_list = Gtk.ListBox()
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.add_css_class("navigation-sidebar")
        self.nav_list.connect("row-selected", self._on_nav_selected)

        self.nav_items = [
            ("dashboard", "Overview", "view-grid-symbolic"),
            ("processes", "Processes", "application-x-executable-symbolic"),
            ("cpu", "CPU", "cpu-symbolic"),
            ("memory", "Memory", "drive-multidisk-symbolic"),
            ("gpu", "GPU", "video-display-symbolic"),
            ("disk", "Disk", "drive-harddisk-symbolic"),
            ("network", "Network", "network-wireless-symbolic"),
            ("battery", "Battery", "battery-symbolic"),
            ("sensors", "Hardware Sensors", "weather-clear-symbolic"),
            ("settings", "Settings", "emblem-system-symbolic"),
        ]

        self.sidebar_rows = {}
        for tag, title, icon_name in self.nav_items:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_box.set_margin_start(10)
            row_box.set_margin_end(10)
            row_box.set_margin_top(8)
            row_box.set_margin_bottom(8)

            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(18)

            lbl = Gtk.Label(label=title)
            lbl.set_halign(Gtk.Align.START)

            row_box.append(icon)
            row_box.append(lbl)
            row.set_child(row_box)
            row.tag = tag

            self.nav_list.append(row)
            self.sidebar_rows[tag] = row

        box.append(self.nav_list)
        # Select first row
        if "dashboard" in self.sidebar_rows:
            self.nav_list.select_row(self.sidebar_rows["dashboard"])

        return box

    def _on_close_request(self, window):
        self._running = False
        self._wake_event.set()
        if self._poll_timer_id:
            GLib.source_remove(self._poll_timer_id)
            self._poll_timer_id = None
        return False

    def _on_nav_selected(self, listbox, row):
        if row and hasattr(row, "tag"):
            self.stack.set_visible_child_name(row.tag)
            if row.tag == "processes":
                # Immediately wake worker to ensure up-to-date process list upon navigation
                self._last_proc_tick = 0.0
                self._wake_event.set()
            elif self._latest_shared_data:
                self._update_visible_page(row.tag, self._latest_shared_data)

    def navigate_to_page(self, page_name: str):
        if page_name in self.sidebar_rows:
            self.nav_list.select_row(self.sidebar_rows[page_name])

    def _setup_timer(self):
        if self._poll_timer_id:
            GLib.source_remove(self._poll_timer_id)
            self._poll_timer_id = None
        
        interval_sec = max(0.5, float(self.config_mgr.get("refresh_interval_sec", 1.0)))
        interval_ms = int(interval_sec * 1000)
        self._poll_timer_id = GLib.timeout_add(interval_ms, self._on_poll_tick)

    def _on_config_changed(self):
        self._setup_timer()

    def _on_poll_tick(self) -> bool:
        if not self._running:
            return False

        # If window is unmapped / minimized, dynamically throttle collection to save CPU
        if not self.get_mapped():
            self._unmapped_tick_count = getattr(self, "_unmapped_tick_count", 0) + 1
            if self._unmapped_tick_count % 3 != 0:
                return True

        self._wake_event.set()
        return True

    def _worker_loop(self):
        while self._running:
            # Wait for wake trigger or timeout fallback
            self._wake_event.wait(timeout=2.0)
            self._wake_event.clear()
            if not self._running:
                break

            now = time.time()
            try:
                cpu_data = self.cpu_collector.update()
                mem_data = self.mem_collector.update()
                gpu_data = self.gpu_collector.update()
                disk_data = self.disk_collector.update()
                net_data = self.net_collector.update()
                bat_data = self.bat_collector.update()
                sensors_data = self.sensors_collector.update()

                proc_interval = float(self.config_mgr.get("process_refresh_interval_sec", 2.0))
                current_page = self.stack.get_visible_child_name()
                effective_proc_interval = proc_interval if current_page == "processes" else 10.0

                proc_data = {}
                if now - self._last_proc_tick >= effective_proc_interval or not self.page_processes.raw_processes:
                    self._last_proc_tick = now
                    proc_data = self.proc_collector.update()

                shared_data = {
                    "cpu": cpu_data,
                    "memory": mem_data,
                    "gpu": gpu_data,
                    "disk": disk_data,
                    "network": net_data,
                    "battery": bat_data,
                    "sensors": sensors_data,
                    "process": proc_data,
                }

                if self._running:
                    GLib.idle_add(self._apply_metrics_on_ui, shared_data)
            except Exception:
                pass

    def _update_visible_page(self, page_name: str, shared_data: dict):
        if page_name == "dashboard":
            self.page_dashboard.update_metrics(shared_data)
        elif page_name == "cpu":
            self.page_cpu.update_metrics(shared_data)
        elif page_name == "memory":
            self.page_memory.update_metrics(shared_data)
        elif page_name == "gpu":
            self.page_gpu.update_metrics(shared_data)
        elif page_name == "disk":
            self.page_disk.update_metrics(shared_data)
        elif page_name == "network":
            self.page_network.update_metrics(shared_data)
        elif page_name == "battery":
            self.page_battery.update_metrics(shared_data)
        elif page_name == "sensors":
            self.page_sensors.update_metrics(shared_data)
        elif page_name == "processes":
            if shared_data.get("process") or not self.page_processes.raw_processes:
                self.page_processes.update_metrics(shared_data)

    def _apply_metrics_on_ui(self, shared_data: dict):
        if not self._running:
            return

        self._latest_shared_data = shared_data

        current_w = self.get_width()
        if current_w > 0 and current_w != getattr(self, "_last_window_w", 0):
            self._last_window_w = current_w
            self.page_processes.set_responsive_layout(current_w)

        current_page = self.stack.get_visible_child_name()
        self._update_visible_page(current_page, shared_data)
