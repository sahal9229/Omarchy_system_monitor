"""
Windows 11 Task Manager style dashboard summary card.
Features an icon, headline metric value, mini sparkline, and navigation callback.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from typing import Callable, Optional, Tuple, List
from .graph import RealtimeGraph

class MetricCard(Gtk.Button):
    def __init__(self, 
                 title: str, 
                 icon_name: str,
                 line_color: Tuple[float, float, float] = (0.2, 0.6, 1.0),
                 on_click_page: Optional[str] = None,
                 navigate_cb: Optional[Callable[[str], None]] = None):
        super().__init__()
        self.on_click_page = on_click_page
        self.navigate_cb = navigate_cb
        
        self.add_css_class("flat")
        self.set_hexpand(True)

        # Card container box
        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card_box.add_css_class("card")
        card_box.set_margin_start(4)
        card_box.set_margin_end(4)
        card_box.set_margin_top(4)
        card_box.set_margin_bottom(4)
        card_box.set_size_request(220, 150)

        # Top row: icon + title + current primary value
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_row.set_margin_start(12)
        top_row.set_margin_end(12)
        top_row.set_margin_top(12)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(20)
        icon.add_css_class("accent")

        self.title_label = Gtk.Label(label=title)
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.set_hexpand(True)
        self.title_label.add_css_class("title-4")

        self.val_label = Gtk.Label(label="0%")
        self.val_label.set_halign(Gtk.Align.END)
        self.val_label.add_css_class("title-2")

        top_row.append(icon)
        top_row.append(self.title_label)
        top_row.append(self.val_label)
        card_box.append(top_row)

        # Mini Sparkline Graph
        self.graph = RealtimeGraph(line_color=line_color, fill_opacity=0.2, show_grid=False)
        self.graph.set_content_height(55)
        self.graph.set_margin_start(12)
        self.graph.set_margin_end(12)
        card_box.append(self.graph)

        # Bottom detail subtitle
        self.subtitle_label = Gtk.Label(label="--")
        self.subtitle_label.set_halign(Gtk.Align.START)
        self.subtitle_label.set_margin_start(12)
        self.subtitle_label.set_margin_end(12)
        self.subtitle_label.set_margin_bottom(10)
        self.subtitle_label.add_css_class("caption")
        self.subtitle_label.add_css_class("dim-label")
        card_box.append(self.subtitle_label)

        self.set_child(card_box)

        if self.on_click_page and self.navigate_cb:
            self.connect("clicked", self._on_clicked)

    def _on_clicked(self, btn):
        if self.on_click_page and self.navigate_cb:
            self.navigate_cb(self.on_click_page)

    def update_data(self, primary_val: str, history: List[float], subtitle: str):
        if self.val_label.get_label() != primary_val:
            self.val_label.set_label(primary_val)
        if self.subtitle_label.get_label() != subtitle:
            self.subtitle_label.set_label(subtitle)
        self.graph.set_data(history)
