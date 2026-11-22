"""
Dashboard overview page.
Contains real-time summary cards for CPU, Memory, GPU, Disk, Network, Battery, and Temperature.
Clicking any card smoothly navigates to its dedicated detailed view.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from typing import Callable, Dict
from ..widgets.metric_card import MetricCard

class DashboardPage(Gtk.ScrolledWindow):
    def __init__(self, navigate_cb: Callable[[str], None], config_mgr):
        super().__init__()
        self.navigate_cb = navigate_cb
        self.config_mgr = config_mgr

        self.set_vexpand(True)
        self.set_hexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(20)
        content.set_margin_bottom(24)

        # Header Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label="System Overview")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        subtitle = Gtk.Label(label="Real-time performance summary and hardware health")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")

        title_box.append(title)
        title_box.append(subtitle)
        content.append(title_box)

        # FlowGrid of Cards
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(3)
        self.flowbox.set_min_children_per_line(1)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_column_spacing(12)
        self.flowbox.set_row_spacing(12)

        # Create Cards
        self.cards: Dict[str, MetricCard] = {}

        # CPU Card (Blue)
        self.cards["cpu"] = MetricCard(
            title="CPU",
            icon_name="cpu-symbolic",
            line_color=(0.18, 0.53, 0.95),
            on_click_page="cpu",
            navigate_cb=self.navigate_cb
        )

        # Memory Card (Purple)
        self.cards["memory"] = MetricCard(
            title="Memory",
            icon_name="drive-multidisk-symbolic",
            line_color=(0.65, 0.35, 0.95),
            on_click_page="memory",
            navigate_cb=self.navigate_cb
        )

        # GPU Card (Teal)
        self.cards["gpu"] = MetricCard(
            title="GPU",
            icon_name="video-display-symbolic",
            line_color=(0.15, 0.75, 0.75),
            on_click_page="gpu",
            navigate_cb=self.navigate_cb
        )

        # Disk Card (Green)
        self.cards["disk"] = MetricCard(
            title="Disk",
            icon_name="drive-harddisk-symbolic",
            line_color=(0.20, 0.75, 0.40),
            on_click_page="disk",
            navigate_cb=self.navigate_cb
        )

        # Network Card (Orange)
        self.cards["network"] = MetricCard(
            title="Network",
            icon_name="network-wireless-symbolic",
            line_color=(0.95, 0.55, 0.15),
            on_click_page="network",
            navigate_cb=self.navigate_cb
        )

        # Battery Card (Yellow/Amber)
        self.cards["battery"] = MetricCard(
            title="Battery",
            icon_name="battery-symbolic",
            line_color=(0.92, 0.75, 0.15),
            on_click_page="battery",
            navigate_cb=self.navigate_cb
        )

        # Temperature / Fan Card (Red/Coral)
        self.cards["temperature"] = MetricCard(
            title="Thermal / Fan",
            icon_name="weather-clear-symbolic",
            line_color=(0.95, 0.30, 0.30),
            on_click_page="sensors",
            navigate_cb=self.navigate_cb
        )

        for card in self.cards.values():
            self.flowbox.append(card)

        content.append(self.flowbox)
        self.set_child(content)

    def update_metrics(self, data: dict):
        # CPU
        cpu = data.get("cpu", {})
        if self.config_mgr.get_show_card("cpu"):
            self.cards["cpu"].set_visible(True)
            pct = cpu.get("overall_percent", 0.0)
            cur_f = cpu.get("current_frequency_mhz")
            f_str = f"{cur_f/1000.0:.2f} GHz" if cur_f else "--"
            cores = cpu.get("logical_processors", 1)
            self.cards["cpu"].update_data(
                primary_val=f"{pct:.0f}%",
                history=cpu.get("overall_history", []),
                subtitle=f"{f_str} • {cores} Threads"
            )
        else:
            self.cards["cpu"].set_visible(False)

        # Memory
        mem = data.get("memory", {})
        if self.config_mgr.get_show_card("memory"):
            self.cards["memory"].set_visible(True)
            mpct = mem.get("ram_percent", 0.0)
            used_gb = mem.get("used_ram", 0) / (1024**3)
            tot_gb = mem.get("total_ram", 1) / (1024**3)
            self.cards["memory"].update_data(
                primary_val=f"{mpct:.0f}%",
                history=mem.get("ram_history", []),
                subtitle=f"{used_gb:.1f} / {tot_gb:.1f} GB ({mpct:.0f}%)"
            )
        else:
            self.cards["memory"].set_visible(False)

        # GPU
        gpu = data.get("gpu", {})
        if self.config_mgr.get_show_card("gpu"):
            self.cards["gpu"].set_visible(True)
            gpct = gpu.get("usage_percent")
            g_str = f"{gpct:.0f}%" if gpct is not None else "--"
            g_hist = gpu.get("usage_history", [])
            g_name = gpu.get("vendor", "GPU")
            self.cards["gpu"].update_data(
                primary_val=g_str,
                history=g_hist,
                subtitle=f"{g_name} • {gpu.get('memory_type', '')}"
            )
        else:
            self.cards["gpu"].set_visible(False)

        # Disk
        disk = data.get("disk", {})
        if self.config_mgr.get_show_card("disk"):
            self.cards["disk"].set_visible(True)
            r_bps = disk.get("read_speed_bps", 0.0)
            w_bps = disk.get("write_speed_bps", 0.0)
            io_total_mb = (r_bps + w_bps) / (1024 * 1024)
            st_pct = disk.get("storage_percent", 0.0)
            self.cards["disk"].update_data(
                primary_val=f"{io_total_mb:.1f} MB/s",
                history=disk.get("read_history", []),
                subtitle=f"{st_pct:.0f}% Space Used • {disk.get('primary_device', 'Disk')}"
            )
        else:
            self.cards["disk"].set_visible(False)

        # Network
        net = data.get("network", {})
        if self.config_mgr.get_show_card("network"):
            self.cards["network"].set_visible(True)
            rx_bps = net.get("total_rx_bps", 0.0)
            tx_bps = net.get("total_tx_bps", 0.0)
            
            # Format speed nicely
            def fmt_spd(b):
                if b >= 1024*1024:
                    return f"{b/(1024*1024):.1f} MB/s"
                elif b >= 1024:
                    return f"{b/1024:.0f} KB/s"
                return f"{b:.0f} B/s"

            self.cards["network"].update_data(
                primary_val=fmt_spd(rx_bps),
                history=net.get("rx_history", []),
                subtitle=f"↓ {fmt_spd(rx_bps)} • ↑ {fmt_spd(tx_bps)}"
            )
        else:
            self.cards["network"].set_visible(False)

        # Battery
        bat = data.get("battery", {})
        if self.config_mgr.get_show_card("battery") and bat.get("present"):
            self.cards["battery"].set_visible(True)
            bpct = bat.get("percentage")
            b_str = f"{bpct}%" if bpct is not None else "--"
            b_stat = bat.get("status", "Unknown")
            p_w = bat.get("power_w")
            p_str = f" • {p_w:.1f}W" if p_w is not None else ""
            self.cards["battery"].update_data(
                primary_val=b_str,
                history=[bpct or 0.0] * 60,
                subtitle=f"{b_stat}{p_str}"
            )
        else:
            self.cards["battery"].set_visible(False)

        # Thermal / Fan
        sensors = data.get("sensors", {})
        if self.config_mgr.get_show_card("temperature"):
            self.cards["temperature"].set_visible(True)
            c_temp = sensors.get("primary_cpu_temp_c")
            temp_str = f"{c_temp:.0f}°C" if c_temp is not None else "--"
            fan_rpm = sensors.get("primary_fan_rpm")
            fan_str = f"{fan_rpm} RPM" if fan_rpm is not None else "Fan N/A"
            self.cards["temperature"].update_data(
                primary_val=temp_str,
                history=[c_temp or 0.0] * 60,
                subtitle=f"CPU Temp • {fan_str}"
            )
        else:
            self.cards["temperature"].set_visible(False)
