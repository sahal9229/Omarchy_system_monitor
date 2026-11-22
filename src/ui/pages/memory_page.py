"""
Detailed Memory and Swap performance page.
Shows real-time graphs, RAM composition breakdown, and Swap status.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from ..widgets.graph import RealtimeGraph
from ..widgets.stat_row import StatRow

class MemoryPage(Gtk.ScrolledWindow):
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
        title = Gtk.Label(label="Memory")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        self.summary_label = Gtk.Label(label="-- GB RAM Total")
        self.summary_label.set_halign(Gtk.Align.START)
        self.summary_label.add_css_class("dim-label")

        title_box.append(title)
        title_box.append(self.summary_label)
        content.append(title_box)

        # Main RAM Graph Card
        ram_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        ram_card.add_css_class("card")

        ram_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        ram_header.set_margin_start(16)
        ram_header.set_margin_end(16)
        ram_header.set_margin_top(12)

        ram_title = Gtk.Label(label="RAM Usage (60 Seconds)")
        ram_title.set_halign(Gtk.Align.START)
        ram_title.set_hexpand(True)
        ram_title.add_css_class("heading")

        self.ram_val_label = Gtk.Label(label="0%")
        self.ram_val_label.set_halign(Gtk.Align.END)
        self.ram_val_label.add_css_class("title-2")

        ram_header.append(ram_title)
        ram_header.append(self.ram_val_label)
        ram_card.append(ram_header)

        self.ram_graph = RealtimeGraph(
            line_color=(0.65, 0.35, 0.95),
            fill_opacity=0.25,
            min_val=0.0,
            max_val=100.0,
            unit="%"
        )
        self.ram_graph.set_content_height(140)
        self.ram_graph.set_margin_start(16)
        self.ram_graph.set_margin_end(16)
        self.ram_graph.set_margin_bottom(16)
        ram_card.append(self.ram_graph)
        content.append(ram_card)

        # Swap Graph Card
        swap_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        swap_card.add_css_class("card")

        swap_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        swap_header.set_margin_start(16)
        swap_header.set_margin_end(16)
        swap_header.set_margin_top(12)

        swap_title = Gtk.Label(label="Swap Usage (60 Seconds)")
        swap_title.set_halign(Gtk.Align.START)
        swap_title.set_hexpand(True)
        swap_title.add_css_class("heading")

        self.swap_val_label = Gtk.Label(label="0%")
        self.swap_val_label.set_halign(Gtk.Align.END)
        self.swap_val_label.add_css_class("title-2")

        swap_header.append(swap_title)
        swap_header.append(self.swap_val_label)
        swap_card.append(swap_header)

        self.swap_graph = RealtimeGraph(
            line_color=(0.85, 0.35, 0.65),
            fill_opacity=0.20,
            min_val=0.0,
            max_val=100.0,
            unit="%"
        )
        self.swap_graph.set_content_height(100)
        self.swap_graph.set_margin_start(16)
        self.swap_graph.set_margin_end(16)
        self.swap_graph.set_margin_bottom(16)
        swap_card.append(self.swap_graph)
        content.append(swap_card)

        # Stats Details
        stats_group = Adw.PreferencesGroup()
        stats_group.set_title("Memory Composition and Swap Details")

        self.stat_in_use = StatRow("In Use (RAM)", "-- GB")
        self.stat_available = StatRow("Available (RAM)", "-- GB")
        self.stat_free = StatRow("Completely Free", "-- GB")
        self.stat_cached = StatRow("Cached & Buffers", "-- GB")
        self.stat_total_ram = StatRow("Physical Total", "-- GB")
        self.stat_swap_used = StatRow("Swap Used", "-- MB")
        self.stat_swap_total = StatRow("Swap Total", "-- GB")

        stats_group.add(self.stat_in_use)
        stats_group.add(self.stat_available)
        stats_group.add(self.stat_cached)
        stats_group.add(self.stat_free)
        stats_group.add(self.stat_total_ram)
        stats_group.add(self.stat_swap_used)
        stats_group.add(self.stat_swap_total)
        content.append(stats_group)

        self.set_child(content)

    def update_metrics(self, data: dict):
        mem = data.get("memory", {})
        if not mem:
            return

        total_b = mem.get("total_ram", 1)
        used_b = mem.get("used_ram", 0)
        avail_b = mem.get("available_ram", 0)
        free_b = mem.get("free_ram", 0)
        cached_b = mem.get("cached_ram", 0)
        ram_pct = mem.get("ram_percent", 0.0)

        total_gb = total_b / (1024**3)
        used_gb = used_b / (1024**3)
        avail_gb = avail_b / (1024**3)
        free_gb = free_b / (1024**3)
        cached_gb = cached_b / (1024**3)

        self.summary_label.set_label(f"{total_gb:.1f} GB Total Installed RAM")
        self.ram_val_label.set_label(f"{ram_pct:.0f}%")
        self.ram_graph.set_data(mem.get("ram_history", []))

        self.stat_in_use.set_value(f"{used_gb:.2f} GB ({ram_pct:.1f}%)")
        self.stat_available.set_value(f"{avail_gb:.2f} GB")
        self.stat_cached.set_value(f"{cached_gb:.2f} GB")
        self.stat_free.set_value(f"{free_gb:.2f} GB")
        self.stat_total_ram.set_value(f"{total_gb:.2f} GB")

        # Swap
        swap_tot_b = mem.get("total_swap", 0)
        swap_used_b = mem.get("used_swap", 0)
        swap_pct = mem.get("swap_percent", 0.0)

        self.swap_val_label.set_label(f"{swap_pct:.0f}%")
        self.swap_graph.set_data(mem.get("swap_history", []))

        swap_tot_gb = swap_tot_b / (1024**3)
        swap_used_mb = swap_used_b / (1024**2)
        self.stat_swap_used.set_value(f"{swap_used_mb:.1f} MB ({swap_pct:.1f}%)")
        self.stat_swap_total.set_value(f"{swap_tot_gb:.2f} GB")
