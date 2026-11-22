"""
Detailed Network performance page.
Dual live download and upload speed graphs, interface statuses, and network traffic counters.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from ..widgets.graph import RealtimeGraph
from ..widgets.stat_row import StatRow

class NetworkPage(Gtk.ScrolledWindow):
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
        title = Gtk.Label(label="Network")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        self.summary_label = Gtk.Label(label="Network Adapters & Traffic")
        self.summary_label.set_halign(Gtk.Align.START)
        self.summary_label.add_css_class("dim-label")

        title_box.append(title)
        title_box.append(self.summary_label)
        content.append(title_box)

        # Dual Download / Upload Graphs
        graphs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # Download Card (Blue)
        rx_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        rx_card.add_css_class("card")
        rx_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        rx_hdr.set_margin_start(16)
        rx_hdr.set_margin_end(16)
        rx_hdr.set_margin_top(10)
        rx_title = Gtk.Label(label="Download (Receive)")
        rx_title.set_halign(Gtk.Align.START)
        rx_title.set_hexpand(True)
        rx_title.add_css_class("heading")
        self.rx_val_label = Gtk.Label(label="0 KB/s")
        self.rx_val_label.set_halign(Gtk.Align.END)
        self.rx_val_label.add_css_class("title-2")
        rx_hdr.append(rx_title)
        rx_hdr.append(self.rx_val_label)
        rx_card.append(rx_hdr)

        self.rx_graph = RealtimeGraph(
            line_color=(0.18, 0.53, 0.95),
            fill_opacity=0.25,
            min_val=0.0,
            max_val=None, # Auto-scale
            unit="KB/s"
        )
        self.rx_graph.set_content_height(100)
        self.rx_graph.set_margin_start(16)
        self.rx_graph.set_margin_end(16)
        self.rx_graph.set_margin_bottom(12)
        rx_card.append(self.rx_graph)
        graphs_box.append(rx_card)

        # Upload Card (Amber)
        tx_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        tx_card.add_css_class("card")
        tx_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        tx_hdr.set_margin_start(16)
        tx_hdr.set_margin_end(16)
        tx_hdr.set_margin_top(10)
        tx_title = Gtk.Label(label="Upload (Transmit)")
        tx_title.set_halign(Gtk.Align.START)
        tx_title.set_hexpand(True)
        tx_title.add_css_class("heading")
        self.tx_val_label = Gtk.Label(label="0 KB/s")
        self.tx_val_label.set_halign(Gtk.Align.END)
        self.tx_val_label.add_css_class("title-2")
        tx_hdr.append(tx_title)
        tx_hdr.append(self.tx_val_label)
        tx_card.append(tx_hdr)

        self.tx_graph = RealtimeGraph(
            line_color=(0.95, 0.65, 0.15),
            fill_opacity=0.25,
            min_val=0.0,
            max_val=None, # Auto-scale
            unit="KB/s"
        )
        self.tx_graph.set_content_height(100)
        self.tx_graph.set_margin_start(16)
        self.tx_graph.set_margin_end(16)
        self.tx_graph.set_margin_bottom(12)
        tx_card.append(self.tx_graph)
        graphs_box.append(tx_card)
        content.append(graphs_box)

        # Interfaces Group
        self.iface_group = Adw.PreferencesGroup()
        self.iface_group.set_title("Network Adapters")
        self.iface_rows = []
        content.append(self.iface_group)

        self.set_child(content)

    def _format_rate(self, bps: float) -> str:
        if bps >= 1024**2:
            return f"{bps/(1024**2):.2f} MB/s"
        elif bps >= 1024:
            return f"{bps/1024:.1f} KB/s"
        return f"{bps:.0f} B/s"

    def _format_bytes(self, b: float) -> str:
        if b >= 1024**3:
            return f"{b/(1024**3):.2f} GB"
        elif b >= 1024**2:
            return f"{b/(1024**2):.1f} MB"
        return f"{b/1024:.0f} KB"

    def update_metrics(self, data: dict):
        net = data.get("network", {})
        if not net:
            return

        rx_bps = net.get("total_rx_bps", 0.0)
        tx_bps = net.get("total_tx_bps", 0.0)

        self.rx_val_label.set_label(self._format_rate(rx_bps))
        self.tx_val_label.set_label(self._format_rate(tx_bps))

        # Convert to KB/s for graph
        rx_hist_kb = [x / 1024.0 for x in net.get("rx_history", [])]
        tx_hist_kb = [x / 1024.0 for x in net.get("tx_history", [])]
        self.rx_graph.set_data(rx_hist_kb)
        self.tx_graph.set_data(tx_hist_kb)

        interfaces = net.get("interfaces", [])
        if len(self.iface_rows) != len(interfaces):
            for row in self.iface_rows:
                self.iface_group.remove(row["row"])
            self.iface_rows = []

            for iface in interfaces:
                row = Adw.ActionRow()
                row.set_title(iface["name"])
                row.set_subtitle(f"{iface['type']} • Status: {iface['status'].upper()}")

                lbl = Gtk.Label(label="--")
                lbl.set_halign(Gtk.Align.END)
                lbl.add_css_class("caption")
                row.add_suffix(lbl)

                self.iface_group.add(row)
                self.iface_rows.append({
                    "row": row,
                    "label": lbl,
                    "name": iface["name"]
                })

        for row_item, iface in zip(self.iface_rows, interfaces):
            rx_s = self._format_rate(iface["rx_speed_bps"])
            tx_s = self._format_rate(iface["tx_speed_bps"])
            tot_rx = self._format_bytes(iface["total_rx_bytes"])
            tot_tx = self._format_bytes(iface["total_tx_bytes"])
            row_item["label"].set_label(f"↓ {rx_s} ({tot_rx})   ↑ {tx_s} ({tot_tx})")
            row_item["row"].set_subtitle(f"{iface['type']} • Status: {iface['status'].upper()}")
