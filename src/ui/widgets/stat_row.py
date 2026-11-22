"""
StatRow widget for key-value hardware and metric displays.
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

class StatRow(Gtk.Box):
    def __init__(self, label_text: str, value_text: str = "--"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        self.label = Gtk.Label(label=label_text)
        self.label.set_halign(Gtk.Align.START)
        self.label.set_hexpand(True)
        self.label.add_css_class("dim-label")

        self.value_label = Gtk.Label(label=value_text)
        self.value_label.set_halign(Gtk.Align.END)
        self.value_label.set_selectable(True)
        self.value_label.add_css_class("heading")

        self.append(self.label)
        self.append(self.value_label)

    def set_value(self, text: str):
        self.value_label.set_label(text)
