"""
Detailed CPU performance page.
Shows overall CPU graph, individual logical core graphs, load averages,
frequencies, and processor architecture specifications.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from ..widgets.graph import RealtimeGraph
from ..widgets.stat_row import StatRow
from typing import List

class CPUPage(Gtk.ScrolledWindow):
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
        self.title_label = Gtk.Label(label="CPU")
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.add_css_class("title-1")

        self.model_label = Gtk.Label(label="Detecting CPU...")
        self.model_label.set_halign(Gtk.Align.START)
        self.model_label.add_css_class("dim-label")

        title_box.append(self.title_label)
        title_box.append(self.model_label)
        content.append(title_box)

        # Main Performance Graph Card
        graph_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        graph_card.add_css_class("card")
        graph_card.set_margin_top(4)

        graph_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        graph_header.set_margin_start(16)
        graph_header.set_margin_end(16)
        graph_header.set_margin_top(12)

        g_title = Gtk.Label(label="% Utilization (60 Seconds)")
        g_title.set_halign(Gtk.Align.START)
        g_title.set_hexpand(True)
        g_title.add_css_class("heading")

        self.overall_val_label = Gtk.Label(label="0%")
        self.overall_val_label.set_halign(Gtk.Align.END)
        self.overall_val_label.add_css_class("title-2")

        graph_header.append(g_title)
        graph_header.append(self.overall_val_label)
        graph_card.append(graph_header)

        self.main_graph = RealtimeGraph(
            line_color=(0.18, 0.53, 0.95),
            fill_opacity=0.25,
            min_val=0.0,
            max_val=100.0,
            unit="%"
        )
        self.main_graph.set_content_height(160)
        self.main_graph.set_margin_start(16)
        self.main_graph.set_margin_end(16)
        self.main_graph.set_margin_bottom(16)
        graph_card.append(self.main_graph)
        content.append(graph_card)

        # Stats and Specs Split
        stats_group = Adw.PreferencesGroup()
        stats_group.set_title("CPU Specifications and Metrics")

        self.stat_util = StatRow("Utilization", "0%")
        self.stat_freq = StatRow("Speed", "-- GHz")
        self.stat_cores = StatRow("Cores", "--")
        self.stat_logical = StatRow("Logical Processors", "--")
        self.stat_arch = StatRow("Architecture", "--")
        self.stat_load = StatRow("Load Average (1 / 5 / 15m)", "--")
        self.stat_temp = StatRow("Temperature", "-- °C")

        stats_group.add(self.stat_util)
        stats_group.add(self.stat_freq)
        stats_group.add(self.stat_cores)
        stats_group.add(self.stat_logical)
        stats_group.add(self.stat_arch)
        stats_group.add(self.stat_load)
        stats_group.add(self.stat_temp)
        content.append(stats_group)

        # Per-Core Activity Grid
        cores_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        c_title = Gtk.Label(label="Individual Core Utilization")
        c_title.set_halign(Gtk.Align.START)
        c_title.add_css_class("title-3")
        cores_group.append(c_title)

        self.core_flowbox = Gtk.FlowBox()
        self.core_flowbox.set_max_children_per_line(4)
        self.core_flowbox.set_min_children_per_line(2)
        self.core_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.core_flowbox.set_column_spacing(8)
        self.core_flowbox.set_row_spacing(8)

        self.core_widgets: List[dict] = []
        cores_group.append(self.core_flowbox)
        content.append(cores_group)

        self.set_child(content)

    def _init_cores(self, count: int):
        for _ in range(count):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            card.add_css_class("card")
            card.set_size_request(160, 90)

            lbl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            lbl_box.set_margin_start(8)
            lbl_box.set_margin_end(8)
            lbl_box.set_margin_top(6)

            core_name = Gtk.Label(label=f"Core {len(self.core_widgets)}")
            core_name.set_halign(Gtk.Align.START)
            core_name.set_hexpand(True)
            core_name.add_css_class("caption")

            core_val = Gtk.Label(label="0%")
            core_val.set_halign(Gtk.Align.END)
            core_val.add_css_class("caption")
            core_val.add_css_class("heading")

            lbl_box.append(core_name)
            lbl_box.append(core_val)
            card.append(lbl_box)

            graph = RealtimeGraph(
                line_color=(0.18, 0.53, 0.95),
                fill_opacity=0.15,
                min_val=0.0,
                max_val=100.0,
                show_grid=False
            )
            graph.set_content_height(45)
            graph.set_margin_start(8)
            graph.set_margin_end(8)
            graph.set_margin_bottom(6)
            card.append(graph)

            self.core_flowbox.append(card)
            self.core_widgets.append({
                "card": card,
                "label": core_val,
                "graph": graph
            })

    def update_metrics(self, data: dict):
        cpu = data.get("cpu", {})
        if not cpu:
            return

        self.model_label.set_label(f"{cpu.get('model_name', 'Unknown')} ({cpu.get('architecture', '')})")
        
        overall = cpu.get("overall_percent", 0.0)
        self.overall_val_label.set_label(f"{overall:.0f}%")
        self.stat_util.set_value(f"{overall:.1f}%")

        self.main_graph.set_data(cpu.get("overall_history", []))

        # Speed
        cur_f = cpu.get("current_frequency_mhz")
        if cur_f:
            min_f = cpu.get("min_frequency_mhz", 0)
            max_f = cpu.get("max_frequency_mhz", 0)
            f_str = f"{cur_f/1000.0:.2f} GHz (Range: {min_f/1000.0:.1f} - {max_f/1000.0:.1f} GHz)"
        else:
            f_str = "-- GHz"
        self.stat_freq.set_value(f_str)

        self.stat_cores.set_value(str(cpu.get("physical_cores", "--")))
        self.stat_logical.set_value(str(cpu.get("logical_processors", "--")))
        self.stat_arch.set_value(str(cpu.get("architecture", "--")))

        l1 = cpu.get("load_1m", 0.0)
        l5 = cpu.get("load_5m", 0.0)
        l15 = cpu.get("load_15m", 0.0)
        self.stat_load.set_value(f"{l1:.2f}, {l5:.2f}, {l15:.2f}")

        temp = cpu.get("temperature_c")
        self.stat_temp.set_value(f"{temp:.1f} °C" if temp is not None else "Unavailable")

        # Core grids
        core_pcts = cpu.get("core_percents", [])
        core_histories = cpu.get("core_histories", [])
        if len(self.core_widgets) != len(core_pcts):
            self._init_cores(len(core_pcts))

        for i, (pct, hist) in enumerate(zip(core_pcts, core_histories)):
            if i < len(self.core_widgets):
                self.core_widgets[i]["label"].set_label(f"{pct:.0f}%")
                self.core_widgets[i]["graph"].set_data(hist)
