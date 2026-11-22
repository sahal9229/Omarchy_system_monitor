"""
Hardware Thermals and Cooling telemetry page.
Focuses strictly on key actionable thermal metrics: CPU Package, Core Average,
Hottest Core, NVMe Storage, Chipset, and Cooling Fan RPM, filtering out noise.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from ..widgets.graph import RealtimeGraph
from ..widgets.stat_row import StatRow
from typing import Dict, List, Optional

class SensorsPage(Gtk.ScrolledWindow):
    def __init__(self, config_mgr):
        super().__init__()
        self.config_mgr = config_mgr
        self.set_vexpand(True)
        self.set_hexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(16)
        content.set_margin_bottom(20)

        # Header Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="Hardware Thermals and Cooling")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        subtitle = Gtk.Label(label="Real-time component temperatures and thermal load status")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")
        subtitle.add_css_class("caption")

        title_box.append(title)
        title_box.append(subtitle)
        content.append(title_box)

        # Read-Only Notice
        notice_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        notice_box.add_css_class("card")
        notice_box.set_margin_top(2)

        info_icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
        info_icon.set_pixel_size(20)
        info_icon.set_margin_start(14)
        info_icon.add_css_class("accent")

        notice_text = Gtk.Label(
            label="Read-Only Telemetry: Thermal profiles and cooling fan curves are managed exclusively by firmware and BIOS."
        )
        notice_text.set_wrap(True)
        notice_text.set_hexpand(True)
        notice_text.set_halign(Gtk.Align.START)
        notice_text.set_margin_top(10)
        notice_text.set_margin_bottom(10)
        notice_text.set_margin_end(14)
        notice_text.add_css_class("caption")

        notice_box.append(info_icon)
        notice_box.append(notice_text)
        content.append(notice_box)

        # --- Primary Hero Thermal Card: CPU Thermal Status ---
        hero_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero_card.add_css_class("card")
        hero_card.set_margin_top(4)

        hero_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hero_hdr.set_margin_start(16)
        hero_hdr.set_margin_end(16)
        hero_hdr.set_margin_top(14)

        hdr_left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        h_title = Gtk.Label(label="CPU Thermal Health")
        h_title.set_halign(Gtk.Align.START)
        h_title.add_css_class("title-3")

        self.status_badge = Gtk.Label(label="● Normal / Cool")
        self.status_badge.set_halign(Gtk.Align.START)
        self.status_badge.add_css_class("caption")
        self.status_badge.add_css_class("accent")
        hdr_left.append(h_title)
        hdr_left.append(self.status_badge)

        self.primary_temp_val = Gtk.Label(label="-- °C")
        self.primary_temp_val.set_halign(Gtk.Align.END)
        self.primary_temp_val.add_css_class("title-1")

        hero_hdr.append(hdr_left)
        hero_hdr.append(Gtk.Box(hexpand=True)) # Spacer
        hero_hdr.append(self.primary_temp_val)
        hero_card.append(hero_hdr)

        # Real-time Area Graph
        self.cpu_graph = RealtimeGraph(
            line_color=(0.95, 0.35, 0.35),
            fill_opacity=0.25,
            min_val=25.0,
            max_val=100.0,
            unit="°C"
        )
        self.cpu_graph.set_content_height(130)
        self.cpu_graph.set_margin_start(16)
        self.cpu_graph.set_margin_end(16)
        self.cpu_graph.set_margin_bottom(12)
        hero_card.append(self.cpu_graph)

        content.append(hero_card)

        # --- Key Component Thermal Details ---
        components_group = Adw.PreferencesGroup()
        components_group.set_title("Actionable Hardware Thermals")
        components_group.set_description("Key temperatures that impact system cooling, throttling, and performance")

        # 1. CPU Package
        self.row_cpu_pkg = Adw.ActionRow()
        self.row_cpu_pkg.set_title("CPU Package Temperature")
        self.row_cpu_pkg.set_subtitle("Primary processor socket temperature")
        self.val_cpu_pkg = Gtk.Label(label="--")
        self.val_cpu_pkg.add_css_class("title-3")
        self.row_cpu_pkg.add_suffix(self.val_cpu_pkg)
        components_group.add(self.row_cpu_pkg)

        # 2. CPU Core Average & Hottest Core
        self.row_cpu_avg = Adw.ActionRow()
        self.row_cpu_avg.set_title("CPU Core Average")
        self.row_cpu_avg.set_subtitle("Combined average across all physical processor cores")
        self.val_cpu_avg = Gtk.Label(label="--")
        self.val_cpu_avg.add_css_class("title-3")
        self.row_cpu_avg.add_suffix(self.val_cpu_avg)
        components_group.add(self.row_cpu_avg)

        # 3. Cooling Fan
        self.row_fan = Adw.ActionRow()
        self.row_fan.set_title("Cooling Fan Speed")
        self.row_fan.set_subtitle("Chassis cooling fan (Dell SMM / System Fan)")
        fan_icon = Gtk.Image.new_from_icon_name("weather-windy-symbolic")
        self.row_fan.add_prefix(fan_icon)
        self.val_fan = Gtk.Label(label="-- RPM")
        self.val_fan.add_css_class("title-3")
        self.row_fan.add_suffix(self.val_fan)
        components_group.add(self.row_fan)

        # 4. Storage Drive (NVMe SSD)
        self.row_ssd = Adw.ActionRow()
        self.row_ssd.set_title("Primary NVMe SSD Storage")
        self.row_ssd.set_subtitle("Composite drive temperature (Controller and NAND flash)")
        ssd_icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        self.row_ssd.add_prefix(ssd_icon)
        self.val_ssd = Gtk.Label(label="--")
        self.val_ssd.add_css_class("title-3")
        self.row_ssd.add_suffix(self.val_ssd)
        components_group.add(self.row_ssd)

        # 5. Motherboard / Chipset
        self.row_chipset = Adw.ActionRow()
        self.row_chipset.set_title("Motherboard / Chipset (PCH)")
        self.row_chipset.set_subtitle("Platform Controller Hub thermal state")
        mb_icon = Gtk.Image.new_from_icon_name("weather-clear-symbolic")
        self.row_chipset.add_prefix(mb_icon)
        self.val_chipset = Gtk.Label(label="--")
        self.val_chipset.add_css_class("title-3")
        self.row_chipset.add_suffix(self.val_chipset)
        components_group.add(self.row_chipset)

        content.append(components_group)

        # --- Diagnostic Sensor Diodes (Collapsed by Default) ---
        self.expander_group = Adw.PreferencesGroup()
        self.expander_group.set_title("Diagnostic Diodes (Advanced)")
        self.expander = Adw.ExpanderRow()
        self.expander.set_title("View All Individual Sensor Diodes")
        self.expander.set_subtitle("Raw motherboard, Wi-Fi, and individual core diode readings")
        self.raw_rows: Dict[str, Gtk.Label] = {}
        self.expander_group.add(self.expander)
        content.append(self.expander_group)

        self.set_child(content)

    def _convert_temp(self, c: Optional[float]) -> str:
        if c is None:
            return "Unavailable"
        unit = self.config_mgr.get("temperature_unit", "C")
        if unit == "F":
            f = (c * 9.0 / 5.0) + 32.0
            return f"{f:.1f} °F"
        return f"{c:.1f} °C"

    def update_metrics(self, data: dict):
        sensors = data.get("sensors", {})
        if not sensors:
            return

        # 1. Primary CPU Temp
        pri_cpu = sensors.get("primary_cpu_temp_c")
        cpu_pkg = sensors.get("cpu_package_c")
        cpu_avg = sensors.get("cpu_avg_core_c")
        cpu_max = sensors.get("cpu_max_core_c")

        if pri_cpu is not None:
            self.primary_temp_val.set_label(self._convert_temp(pri_cpu))
            self.cpu_graph.set_data(sensors.get("cpu_history", []))

            # Thermal status badge
            if pri_cpu < 65.0:
                self.status_badge.set_label("● Normal / Cool (Optimal Operating Temp)")
                self.status_badge.remove_css_class("warning")
                self.status_badge.remove_css_class("destructive-action")
                self.status_badge.add_css_class("accent")
            elif pri_cpu < 82.0:
                self.status_badge.set_label("● Warm (Moderate Load)")
                self.status_badge.remove_css_class("accent")
                self.status_badge.remove_css_class("destructive-action")
                self.status_badge.add_css_class("warning")
            else:
                self.status_badge.set_label("● High Thermal Load (Throttling Threshold)")
                self.status_badge.remove_css_class("accent")
                self.status_badge.remove_css_class("warning")
                self.status_badge.add_css_class("destructive-action")

        self.val_cpu_pkg.set_label(self._convert_temp(cpu_pkg))
        if cpu_avg is not None and cpu_max is not None:
            self.val_cpu_avg.set_label(f"{self._convert_temp(cpu_avg)} (Peak: {self._convert_temp(cpu_max)})")
        else:
            self.val_cpu_avg.set_label(self._convert_temp(cpu_avg))

        # 2. Cooling Fan
        fan_rpm = sensors.get("primary_fan_rpm")
        if fan_rpm is not None:
            if fan_rpm == 0:
                self.val_fan.set_label("0 RPM (Passive Cooling)")
                self.row_fan.set_subtitle("Fan idle: Dell EC firmware turns fan off below ~60°C; spins up automatically under load")
            else:
                self.val_fan.set_label(f"{fan_rpm} RPM (Active)")
                self.row_fan.set_subtitle("Fan active: spinning to dissipate system thermal load")
        else:
            self.val_fan.set_label("Unavailable")
            self.row_fan.set_subtitle("No fan tachometer sensor detected")

        # 3. Storage SSD
        ssd_temp = sensors.get("ssd_composite_c")
        self.val_ssd.set_label(self._convert_temp(ssd_temp))

        # 4. Chipset
        chipset_temp = sensors.get("chipset_temp_c")
        self.val_chipset.set_label(self._convert_temp(chipset_temp))

        # 5. Raw Diodes (Populated inside the collapsed expander)
        raw_diodes = sensors.get("raw_diodes", [])
        for d in raw_diodes:
            key = d["key"]
            if key not in self.raw_rows:
                sub_row = Adw.ActionRow()
                sub_row.set_title(d["label"])
                sub_row.set_subtitle(f"Device: {d['device']}")
                val_lbl = Gtk.Label(label="--")
                val_lbl.add_css_class("caption")
                val_lbl.add_css_class("dim-label")
                sub_row.add_suffix(val_lbl)
                self.expander.add_row(sub_row)
                self.raw_rows[key] = val_lbl

            val_lbl = self.raw_rows[key]
            val_lbl.set_label(f"{self._convert_temp(d['current_c'])} (Min: {self._convert_temp(d['min_c'])}, Max: {self._convert_temp(d['max_c'])})")
