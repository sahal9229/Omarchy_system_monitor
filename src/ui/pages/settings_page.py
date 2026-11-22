"""
Settings and preferences page.
Allows configuring theme, refresh intervals, temperature units, and dashboard cards.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

class SettingsPage(Gtk.ScrolledWindow):
    def __init__(self, config_mgr, on_config_changed_cb):
        super().__init__()
        self.config_mgr = config_mgr
        self.on_config_changed_cb = on_config_changed_cb

        self.set_vexpand(True)
        self.set_hexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_margin_top(20)
        content.set_margin_bottom(24)

        # Header Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label="Settings")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        subtitle = Gtk.Label(label="Application preferences and display configuration")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")

        title_box.append(title)
        title_box.append(subtitle)
        content.append(title_box)

        # General Preferences Group
        general_group = Adw.PreferencesGroup()
        general_group.set_title("Appearance and Updates")

        # Theme selection
        theme_row = Adw.ComboRow()
        theme_row.set_title("Application Theme")
        theme_model = Gtk.StringList.new(["System Default", "Dark Theme", "Light Theme"])
        theme_row.set_model(theme_model)

        current_theme = self.config_mgr.get("theme", "system")
        if current_theme == "dark":
            theme_row.set_selected(1)
        elif current_theme == "light":
            theme_row.set_selected(2)
        else:
            theme_row.set_selected(0)

        theme_row.connect("notify::selected", self._on_theme_changed)
        general_group.add(theme_row)

        # Refresh Interval
        refresh_row = Adw.ActionRow()
        refresh_row.set_title("Metrics Refresh Interval")
        refresh_row.set_subtitle("Frequency of hardware metrics polling")

        self.refresh_spin = Gtk.SpinButton.new_with_range(0.5, 5.0, 0.5)
        self.refresh_spin.set_value(float(self.config_mgr.get("refresh_interval_sec", 1.0)))
        self.refresh_spin.set_valign(Gtk.Align.CENTER)
        self.refresh_spin.connect("value-changed", self._on_refresh_changed)
        refresh_row.add_suffix(self.refresh_spin)
        general_group.add(refresh_row)

        # Temperature Unit
        temp_row = Adw.ComboRow()
        temp_row.set_title("Temperature Unit")
        temp_model = Gtk.StringList.new(["Celsius (°C)", "Fahrenheit (°F)"])
        temp_row.set_model(temp_model)
        temp_unit = self.config_mgr.get("temperature_unit", "C")
        temp_row.set_selected(1 if temp_unit == "F" else 0)
        temp_row.connect("notify::selected", self._on_temp_unit_changed)
        general_group.add(temp_row)

        content.append(general_group)

        # Dashboard Card Visibility Group
        card_group = Adw.PreferencesGroup()
        card_group.set_title("Dashboard Cards")
        card_group.set_description("Select which hardware cards to show on the main overview")

        card_keys = [
            ("cpu", "CPU Utilization Card"),
            ("memory", "Memory and Swap Card"),
            ("gpu", "GPU Activity Card"),
            ("disk", "Storage and Disk I/O Card"),
            ("network", "Network Speeds Card"),
            ("battery", "Battery and Power Card"),
            ("temperature", "Thermal and Fan Card"),
        ]

        for key, label in card_keys:
            row = Adw.SwitchRow()
            row.set_title(label)
            row.set_active(self.config_mgr.get_show_card(key))
            row.connect("notify::active", self._make_card_switch_handler(key))
            card_group.add(row)

        content.append(card_group)

        # Reset Section
        reset_group = Adw.PreferencesGroup()
        reset_row = Adw.ActionRow()
        reset_row.set_title("Reset Settings")
        reset_row.set_subtitle("Restore all preferences to default values")

        reset_btn = Gtk.Button(label="Reset")
        reset_btn.set_valign(Gtk.Align.CENTER)
        reset_btn.connect("clicked", self._on_reset_clicked)
        reset_row.add_suffix(reset_btn)
        reset_group.add(reset_row)
        content.append(reset_group)

        self.set_child(content)

    def _on_theme_changed(self, row, param):
        idx = row.get_selected()
        theme_str = "system" if idx == 0 else ("dark" if idx == 1 else "light")
        self.config_mgr.set("theme", theme_str)
        self._apply_theme(theme_str)

    def _apply_theme(self, theme_str: str):
        style_mgr = Adw.StyleManager.get_default()
        if theme_str == "dark":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        elif theme_str == "light":
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _on_refresh_changed(self, spin):
        val = spin.get_value()
        self.config_mgr.set("refresh_interval_sec", val)
        if self.on_config_changed_cb:
            self.on_config_changed_cb()

    def _on_temp_unit_changed(self, row, param):
        unit = "F" if row.get_selected() == 1 else "C"
        self.config_mgr.set("temperature_unit", unit)

    def _make_card_switch_handler(self, card_key: str):
        def handler(row, param):
            self.config_mgr.set_show_card(card_key, row.get_active())
        return handler

    def _on_reset_clicked(self, btn):
        self.config_mgr.reset_to_defaults()
        self._apply_theme("system")
        if self.on_config_changed_cb:
            self.on_config_changed_cb()
