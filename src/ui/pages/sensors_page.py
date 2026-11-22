"""
Hardware sensors and Fan RPM monitoring page.
Strictly READ-ONLY. Displays thermal sensors and fan speeds with session min/max records.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from ..widgets.graph import RealtimeGraph
from ..widgets.stat_row import StatRow
from typing import Dict, List

class SensorsPage(Gtk.ScrolledWindow):
    def __init__(self, config_mgr):
        super().__init__()
        self.config_mgr = config_mgr
        self.set_vexpand(True)
        self.set_hexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(20)
        content.set_margin_bottom(24)

        # Header Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label="Hardware Sensors")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        subtitle = Gtk.Label(label="Live temperatures, Fan RPM, and session extremes")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")

        title_box.append(title)
        title_box.append(subtitle)
        content.append(title_box)

        # Safety / Read-Only Alert Banner
        banner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        banner_box.add_css_class("card")
        banner_box.set_margin_top(4)

        info_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        info_icon.set_pixel_size(24)
        info_icon.set_margin_start(16)
        info_icon.add_css_class("accent")

        banner_text = Gtk.Label(
            label="Read-Only Hardware Monitor: Fan speed curves and cooling states are managed exclusively by firmware and BIOS. This tool strictly performs read-only sensor telemetry."
        )
        banner_text.set_wrap(True)
        banner_text.set_hexpand(True)
        banner_text.set_halign(Gtk.Align.START)
        banner_text.set_margin_top(12)
        banner_text.set_margin_bottom(12)
        banner_text.set_margin_end(16)
        banner_text.add_css_class("caption")

        banner_box.append(info_icon)
        banner_box.append(banner_text)
        content.append(banner_box)

        # Fan RPM Card
        self.fan_group = Adw.PreferencesGroup()
        self.fan_group.set_title("Cooling Fans (Read-Only)")
        self.fan_rows: List[dict] = []
        content.append(self.fan_group)

        # Temperatures Container Group
        self.temps_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.append(self.temps_container)

        self.device_groups: Dict[str, dict] = {}

        self.set_child(content)

    def _convert_temp(self, c: float) -> str:
        unit = self.config_mgr.get("temperature_unit", "C")
        if unit == "F":
            f = (c * 9.0 / 5.0) + 32.0
            return f"{f:.1f} °F"
        return f"{c:.1f} °C"

    def update_metrics(self, data: dict):
        sensors = data.get("sensors", {})
        if not sensors:
            return

        devices = sensors.get("devices", [])

        # Update Fans
        all_fans = []
        for dev in devices:
            for fan in dev.get("fans", []):
                all_fans.append(fan)

        if len(self.fan_rows) != len(all_fans):
            for r in self.fan_rows:
                self.fan_group.remove(r["row"])
            self.fan_rows = []

            if not all_fans:
                no_fan_row = Adw.ActionRow()
                no_fan_row.set_title("Fan RPM Status")
                no_fan_row.set_subtitle("Fan RPM sensor unavailable on this platform")
                self.fan_group.add(no_fan_row)
                self.fan_rows.append({"row": no_fan_row, "val_label": None})
            else:
                for fan in all_fans:
                    row = Adw.ActionRow()
                    row.set_title(fan["label"])
                    icon = Gtk.Image.new_from_icon_name("weather-windy-symbolic")
                    row.add_prefix(icon)

                    v_lbl = Gtk.Label(label="-- RPM")
                    v_lbl.set_halign(Gtk.Align.END)
                    v_lbl.add_css_class("title-3")
                    row.add_suffix(v_lbl)

                    self.fan_group.add(row)
                    self.fan_rows.append({"row": row, "val_label": v_lbl})

        for r_item, fan in zip(self.fan_rows, all_fans):
            if r_item["val_label"]:
                rpm = fan["rpm"]
                if rpm == 0:
                    r_item["val_label"].set_label("0 RPM (Idle)")
                else:
                    r_item["val_label"].set_label(f"{rpm} RPM")

        # Update Temperature Devices
        for dev in devices:
            dev_id = dev["hwmon_id"]
            dev_name = dev["device_name"]
            temps = dev.get("temperatures", [])
            if not temps:
                continue

            if dev_id not in self.device_groups:
                pref_group = Adw.PreferencesGroup()
                pref_group.set_title(f"Thermal Sensors — {dev_name.upper()} ({dev_id})")
                self.temps_container.append(pref_group)
                self.device_groups[dev_id] = {
                    "group": pref_group,
                    "rows": {}
                }

            group_data = self.device_groups[dev_id]
            for t in temps:
                key = t["key"]
                if key not in group_data["rows"]:
                    row = Adw.ActionRow()
                    row.set_title(t["label"])

                    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

                    # Mini graph
                    sparkline = RealtimeGraph(
                        line_color=(0.95, 0.35, 0.35),
                        fill_opacity=0.15,
                        min_val=20.0,
                        max_val=105.0,
                        show_grid=False
                    )
                    sparkline.set_size_request(80, 32)
                    box.append(sparkline)

                    # Value label
                    v_lbl = Gtk.Label(label="--")
                    v_lbl.set_halign(Gtk.Align.END)
                    v_lbl.set_size_request(70, -1)
                    v_lbl.add_css_class("heading")
                    box.append(v_lbl)

                    row.add_suffix(box)
                    group_data["group"].add(row)
                    group_data["rows"][key] = {
                        "row": row,
                        "sparkline": sparkline,
                        "v_lbl": v_lbl
                    }

                # Update row
                r_item = group_data["rows"][key]
                cur_str = self._convert_temp(t["current_c"])
                min_str = self._convert_temp(t["min_c"])
                max_str = self._convert_temp(t["max_c"])

                r_item["v_lbl"].set_label(cur_str)
                r_item["row"].set_subtitle(f"Min: {min_str}   Max: {max_str}")
                r_item["sparkline"].set_data(t["history"])
