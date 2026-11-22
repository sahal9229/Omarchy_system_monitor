"""
Detailed Disk and Filesystem performance page.
Dual read/write real-time graphs, primary drive activity, and mounted filesystem capacity tables.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from ..widgets.graph import RealtimeGraph
from ..widgets.stat_row import StatRow
from typing import List

class DiskPage(Gtk.ScrolledWindow):
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
        title = Gtk.Label(label="Disk")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        self.summary_label = Gtk.Label(label="Storage & Drive Activity")
        self.summary_label.set_halign(Gtk.Align.START)
        self.summary_label.add_css_class("dim-label")

        title_box.append(title)
        title_box.append(self.summary_label)
        content.append(title_box)

        # Dual Read / Write Graphs
        graphs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        # Read Speed Card
        read_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        read_card.add_css_class("card")
        r_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        r_hdr.set_margin_start(16)
        r_hdr.set_margin_end(16)
        r_hdr.set_margin_top(10)
        r_title = Gtk.Label(label="Read Speed")
        r_title.set_halign(Gtk.Align.START)
        r_title.set_hexpand(True)
        r_title.add_css_class("heading")
        self.r_val_label = Gtk.Label(label="0.0 MB/s")
        self.r_val_label.set_halign(Gtk.Align.END)
        self.r_val_label.add_css_class("title-2")
        r_hdr.append(r_title)
        r_hdr.append(self.r_val_label)
        read_card.append(r_hdr)

        self.read_graph = RealtimeGraph(
            line_color=(0.20, 0.75, 0.40),
            fill_opacity=0.25,
            min_val=0.0,
            max_val=None, # Auto-scale
            unit="MB/s"
        )
        self.read_graph.set_content_height(100)
        self.read_graph.set_margin_start(16)
        self.read_graph.set_margin_end(16)
        self.read_graph.set_margin_bottom(12)
        read_card.append(self.read_graph)
        graphs_box.append(read_card)

        # Write Speed Card
        write_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        write_card.add_css_class("card")
        w_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        w_hdr.set_margin_start(16)
        w_hdr.set_margin_end(16)
        w_hdr.set_margin_top(10)
        w_title = Gtk.Label(label="Write Speed")
        w_title.set_halign(Gtk.Align.START)
        w_title.set_hexpand(True)
        w_title.add_css_class("heading")
        self.w_val_label = Gtk.Label(label="0.0 MB/s")
        self.w_val_label.set_halign(Gtk.Align.END)
        self.w_val_label.add_css_class("title-2")
        w_hdr.append(w_title)
        w_hdr.append(self.w_val_label)
        write_card.append(w_hdr)

        self.write_graph = RealtimeGraph(
            line_color=(0.95, 0.55, 0.15),
            fill_opacity=0.25,
            min_val=0.0,
            max_val=None, # Auto-scale
            unit="MB/s"
        )
        self.write_graph.set_content_height(100)
        self.write_graph.set_margin_start(16)
        self.write_graph.set_margin_end(16)
        self.write_graph.set_margin_bottom(12)
        write_card.append(self.write_graph)
        graphs_box.append(write_card)
        content.append(graphs_box)

        # Drive Specs Details
        drive_group = Adw.PreferencesGroup()
        drive_group.set_title("Physical Drive Activity")

        self.stat_primary_dev = StatRow("Primary Storage Device", "--")
        self.stat_read_rate = StatRow("Current Read Rate", "0.0 MB/s")
        self.stat_write_rate = StatRow("Current Write Rate", "0.0 MB/s")
        self.stat_ssd_temp = StatRow("SSD Temperature", "-- °C")

        drive_group.add(self.stat_primary_dev)
        drive_group.add(self.stat_read_rate)
        drive_group.add(self.stat_write_rate)
        drive_group.add(self.stat_ssd_temp)
        content.append(drive_group)

        # Filesystem Usage Group
        self.fs_group = Adw.PreferencesGroup()
        self.fs_group.set_title("Mounted Filesystems")
        self.fs_group.set_description("Logical partition storage capacity and utilization")
        self.fs_rows = []
        content.append(self.fs_group)

        self.set_child(content)

    def _format_bytes(self, b: float) -> str:
        if b >= 1024**4:
            return f"{b/(1024**4):.2f} TB"
        elif b >= 1024**3:
            return f"{b/(1024**3):.1f} GB"
        elif b >= 1024**2:
            return f"{b/(1024**2):.1f} MB"
        return f"{b:.0f} B"

    def _format_rate(self, bps: float) -> str:
        if bps >= 1024**2:
            return f"{bps/(1024**2):.1f} MB/s"
        elif bps >= 1024:
            return f"{bps/1024:.0f} KB/s"
        return f"{bps:.0f} B/s"

    def update_metrics(self, data: dict):
        disk = data.get("disk", {})
        if not disk:
            return

        r_bps = disk.get("read_speed_bps", 0.0)
        w_bps = disk.get("write_speed_bps", 0.0)

        self.r_val_label.set_label(self._format_rate(r_bps))
        self.w_val_label.set_label(self._format_rate(w_bps))

        # Convert history bytes to MB/s for graphs
        r_hist_mb = [x / (1024 * 1024) for x in disk.get("read_history", [])]
        w_hist_mb = [x / (1024 * 1024) for x in disk.get("write_history", [])]
        self.read_graph.set_data(r_hist_mb)
        self.write_graph.set_data(w_hist_mb)

        self.stat_primary_dev.set_value(disk.get("primary_device", "Unknown"))
        self.stat_read_rate.set_value(self._format_rate(r_bps))
        self.stat_write_rate.set_value(self._format_rate(w_bps))

        ssd_temp = disk.get("ssd_temperature_c")
        self.stat_ssd_temp.set_value(f"{ssd_temp:.1f} °C" if ssd_temp is not None else "Unavailable")

        # Filesystem rows
        filesystems = disk.get("filesystems", [])
        if len(self.fs_rows) != len(filesystems):
            # Clear old rows
            for row in self.fs_rows:
                self.fs_group.remove(row)
            self.fs_rows = []

            for fs in filesystems:
                exp_row = Adw.ActionRow()
                exp_row.set_title(fs["mount_point"])
                exp_row.set_subtitle(f"{fs['device']} ({fs['filesystem']})")

                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                box.set_valign(Gtk.Align.CENTER)

                lbl = Gtk.Label(label="--")
                lbl.set_halign(Gtk.Align.END)
                lbl.add_css_class("caption")

                pbar = Gtk.ProgressBar()
                pbar.set_size_request(140, 8)

                box.append(lbl)
                box.append(pbar)
                exp_row.add_suffix(box)

                self.fs_group.add(exp_row)
                self.fs_rows.append({
                    "row": exp_row,
                    "label": lbl,
                    "bar": pbar,
                    "mount": fs["mount_point"]
                })

        for row_item, fs in zip(self.fs_rows, filesystems):
            used_str = self._format_bytes(fs["used_bytes"])
            tot_str = self._format_bytes(fs["total_bytes"])
            pct = fs["usage_percent"]
            row_item["label"].set_label(f"{used_str} / {tot_str} ({pct:.0f}%)")
            row_item["bar"].set_fraction(pct / 100.0)
