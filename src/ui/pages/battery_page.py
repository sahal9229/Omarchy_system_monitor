"""
Battery and power metrics page.
Displays charge level, power draw, voltage, health, and estimated remaining time.
Gracefully handles systems without battery hardware.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from ..widgets.stat_row import StatRow

class BatteryPage(Gtk.ScrolledWindow):
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
        title = Gtk.Label(label="Battery & Power")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        self.summary_label = Gtk.Label(label="Battery status and power consumption")
        self.summary_label.set_halign(Gtk.Align.START)
        self.summary_label.add_css_class("dim-label")

        title_box.append(title)
        title_box.append(self.summary_label)
        content.append(title_box)

        # Main Battery Gauge Card
        self.gauge_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.gauge_card.add_css_class("card")
        self.gauge_card.set_margin_top(4)

        gauge_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gauge_header.set_margin_start(16)
        gauge_header.set_margin_end(16)
        gauge_header.set_margin_top(16)

        self.status_icon = Gtk.Image.new_from_icon_name("battery-symbolic")
        self.status_icon.set_pixel_size(24)

        self.status_label = Gtk.Label(label="Unknown")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_hexpand(True)
        self.status_label.set_margin_start(8)
        self.status_label.add_css_class("title-3")

        self.pct_label = Gtk.Label(label="0%")
        self.pct_label.set_halign(Gtk.Align.END)
        self.pct_label.add_css_class("title-1")

        gauge_header.append(self.status_icon)
        gauge_header.append(self.status_label)
        gauge_header.append(self.pct_label)
        self.gauge_card.append(gauge_header)

        # Progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_margin_start(16)
        self.progress_bar.set_margin_end(16)
        self.progress_bar.set_margin_bottom(16)
        self.gauge_card.append(self.progress_bar)
        content.append(self.gauge_card)

        # Not Present Banner
        self.absent_banner = Adw.StatusPage()
        self.absent_banner.set_icon_name("battery-missing-symbolic")
        self.absent_banner.set_title("No Battery Hardware Detected")
        self.absent_banner.set_description("This system is running on continuous AC power or does not expose a battery interface.")
        self.absent_banner.set_visible(False)
        content.append(self.absent_banner)

        # Stats Details
        self.stats_group = Adw.PreferencesGroup()
        self.stats_group.set_title("Power Specifications")

        self.stat_health = StatRow("Battery Health", "--%")
        self.stat_voltage = StatRow("Voltage", "-- V")
        self.stat_power = StatRow("Power Draw / Charge Rate", "-- W")
        self.stat_time_rem = StatRow("Estimated Time Remaining", "--")
        self.stat_model = StatRow("Model & Technology", "--")

        self.stats_group.add(self.stat_health)
        self.stats_group.add(self.stat_voltage)
        self.stats_group.add(self.stat_power)
        self.stats_group.add(self.stat_time_rem)
        self.stats_group.add(self.stat_model)
        content.append(self.stats_group)

        self.set_child(content)

    def update_metrics(self, data: dict):
        bat = data.get("battery", {})
        if not bat or not bat.get("present"):
            self.gauge_card.set_visible(False)
            self.stats_group.set_visible(False)
            self.absent_banner.set_visible(True)
            return

        self.gauge_card.set_visible(True)
        self.stats_group.set_visible(True)
        self.absent_banner.set_visible(False)

        pct = bat.get("percentage")
        status = bat.get("status", "Unknown")

        self.pct_label.set_label(f"{pct}%" if pct is not None else "--")
        self.status_label.set_label(status)
        if pct is not None:
            self.progress_bar.set_fraction(pct / 100.0)

        health = bat.get("health_percent")
        self.stat_health.set_value(f"{health:.1f}%" if health is not None else "Unavailable")

        volt = bat.get("voltage_v")
        self.stat_voltage.set_value(f"{volt:.2f} V" if volt is not None else "Unavailable")

        power = bat.get("power_w")
        self.stat_power.set_value(f"{power:.2f} W" if power is not None else "Unavailable")

        rem_sec = bat.get("time_remaining_sec")
        if rem_sec:
            hours = int(rem_sec // 3600)
            mins = int((rem_sec % 3600) // 60)
            self.stat_time_rem.set_value(f"{hours}h {mins}m")
        else:
            self.stat_time_rem.set_value("Calculating or on AC power")

        model = bat.get("model_name") or "Standard Battery"
        tech = bat.get("technology") or ""
        self.stat_model.set_value(f"{model} ({tech})".strip())
