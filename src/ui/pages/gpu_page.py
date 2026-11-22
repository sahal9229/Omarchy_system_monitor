"""
Detailed GPU performance page.
Shows GPU model, vendor, utilization graphs, frequencies, and memory architecture.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from ..widgets.graph import RealtimeGraph
from ..widgets.stat_row import StatRow

class GPUPage(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_vexpand(True)
        self.set_hexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(20)
        content.set_margin_bottom(24)

        # Header Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.title_label = Gtk.Label(label="GPU")
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.add_css_class("title-1")

        self.model_label = Gtk.Label(label="Detecting GPU...")
        self.model_label.set_halign(Gtk.Align.START)
        self.model_label.add_css_class("dim-label")

        title_box.append(self.title_label)
        title_box.append(self.model_label)
        content.append(title_box)

        # Main Graph Card
        graph_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        graph_card.add_css_class("card")

        graph_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        graph_header.set_margin_start(16)
        graph_header.set_margin_end(16)
        graph_header.set_margin_top(12)

        g_title = Gtk.Label(label="GPU Engine Activity (60 Seconds)")
        g_title.set_halign(Gtk.Align.START)
        g_title.set_hexpand(True)
        g_title.add_css_class("heading")

        self.val_label = Gtk.Label(label="0%")
        self.val_label.set_halign(Gtk.Align.END)
        self.val_label.add_css_class("title-2")

        graph_header.append(g_title)
        graph_header.append(self.val_label)
        graph_card.append(graph_header)

        self.graph = RealtimeGraph(
            line_color=(0.15, 0.75, 0.75),
            fill_opacity=0.25,
            min_val=0.0,
            max_val=100.0,
            unit="%"
        )
        self.graph.set_content_height(160)
        self.graph.set_margin_start(16)
        self.graph.set_margin_end(16)
        self.graph.set_margin_bottom(16)
        graph_card.append(self.graph)
        content.append(graph_card)

        # Stats Details
        stats_group = Adw.PreferencesGroup()
        stats_group.set_title("GPU Hardware Details")

        self.stat_vendor = StatRow("GPU Vendor", "--")
        self.stat_name = StatRow("Device Name", "--")
        self.stat_freq = StatRow("Core Frequency", "-- MHz")
        self.stat_freq_range = StatRow("Frequency Range", "-- MHz")
        self.stat_mem_type = StatRow("Memory Type", "--")
        self.stat_vram = StatRow("Dedicated VRAM", "--")
        self.stat_temp = StatRow("Temperature", "--")
        self.stat_power = StatRow("Power Consumption", "--")

        stats_group.add(self.stat_vendor)
        stats_group.add(self.stat_name)
        stats_group.add(self.stat_freq)
        stats_group.add(self.stat_freq_range)
        stats_group.add(self.stat_mem_type)
        stats_group.add(self.stat_vram)
        stats_group.add(self.stat_temp)
        stats_group.add(self.stat_power)
        content.append(stats_group)

        self.set_child(content)

    def update_metrics(self, data: dict):
        gpu = data.get("gpu", {})
        if not gpu:
            return

        self.model_label.set_label(f"{gpu.get('name', 'Unknown')} ({gpu.get('vendor', '')})")
        self.stat_vendor.set_value(gpu.get("vendor", "--"))
        self.stat_name.set_value(gpu.get("name", "--"))

        pct = gpu.get("usage_percent")
        if pct is not None:
            self.val_label.set_label(f"{pct:.0f}%")
        else:
            self.val_label.set_label("--")
        self.graph.set_data(gpu.get("usage_history", []))

        cur_f = gpu.get("current_frequency_mhz")
        self.stat_freq.set_value(f"{cur_f:.0f} MHz" if cur_f is not None else "Unavailable")

        min_f = gpu.get("min_frequency_mhz")
        max_f = gpu.get("max_frequency_mhz")
        if min_f is not None and max_f is not None:
            self.stat_freq_range.set_value(f"{min_f:.0f} - {max_f:.0f} MHz")
        else:
            self.stat_freq_range.set_value("Unavailable")

        m_type = gpu.get("memory_type", "Dedicated")
        self.stat_mem_type.set_value(m_type)

        v_used = gpu.get("memory_used_bytes")
        v_tot = gpu.get("memory_total_bytes")
        if v_used and v_tot:
            self.stat_vram.set_value(f"{v_used/(1024**2):.0f} / {v_tot/(1024**2):.0f} MB")
        elif m_type == "Unified System Memory":
            self.stat_vram.set_value("Shared with System RAM (Unified)")
        else:
            self.stat_vram.set_value("Not supported by hardware")

        temp = gpu.get("temperature_c")
        self.stat_temp.set_value(f"{temp:.1f} °C" if temp is not None else "Not exposed by driver")

        power = gpu.get("power_w")
        self.stat_power.set_value(f"{power:.1f} W" if power is not None else "Not supported by hardware")
