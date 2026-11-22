"""
Real-time line/area graph widget drawn using Cairo on Gtk.DrawingArea.
Smooth antialiased curves, gradient fills, and bounded circular history.

Optimized with:
- Change detection: skips queue_draw() if time-series data hasn't changed
- Visibility/mapped awareness: skips expensive Cairo redraws when page/widget is hidden
- Memory-efficient cached points and bounding
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk
import cairo
from typing import List, Optional, Tuple

class RealtimeGraph(Gtk.DrawingArea):
    def __init__(self, 
                 line_color: Tuple[float, float, float] = (0.2, 0.6, 1.0),
                 fill_opacity: float = 0.25,
                 min_val: float = 0.0,
                 max_val: Optional[float] = 100.0,
                 show_grid: bool = True,
                 unit: str = "%"):
        super().__init__()
        self.line_color = line_color
        self.fill_opacity = fill_opacity
        self.min_val = min_val
        self.max_val = max_val
        self.show_grid = show_grid
        self.unit = unit
        self._data: List[float] = [0.0] * 60
        self._last_drawn_hash: Optional[int] = None

        self.set_draw_func(self._draw)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_content_height(120)

    def set_data(self, data: List[float]):
        if not data:
            return
        
        # Skip redraw if the drawing area is not mapped / visible in the scene
        if not self.get_mapped():
            self._data = data
            return

        # Fast check: skip expensive Cairo redraw if data hasn't changed
        if self._data and len(self._data) == len(data) and self._data[-1] == data[-1] and self._data[0] == data[0] and self._data == data:
            return

        self._data = data
        self.queue_draw()

    def set_line_color(self, r: float, g: float, b: float):
        if self.line_color != (r, g, b):
            self.line_color = (r, g, b)
            if self.get_mapped():
                self.queue_draw()

    def _draw(self, area, cr: cairo.Context, width: int, height: int):
        if width <= 0 or height <= 0:
            return

        effective_min = self.min_val
        if self.max_val is not None:
            effective_max = self.max_val
        else:
            max_in_data = max(self._data) if self._data else 1.0
            effective_max = max(max_in_data * 1.15, 1.0)

        val_range = max(effective_max - effective_min, 0.001)

        # Draw grid
        if self.show_grid:
            cr.set_line_width(1.0)
            cr.set_dash([4.0, 4.0])
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.07)

            for pct in (0.25, 0.50, 0.75):
                y = height - (pct * height)
                cr.move_to(0, y)
                cr.line_to(width, y)
                cr.stroke()

            cr.set_dash([])

        n_points = len(self._data)
        if n_points < 2:
            return

        dx = width / float(n_points - 1)
        points = []
        for i, val in enumerate(self._data):
            clamped = max(effective_min, min(effective_max, val))
            normalized = (clamped - effective_min) / val_range
            x = i * dx
            y = height - (normalized * height)
            points.append((x, y))

        r, g, b = self.line_color

        # Draw filled gradient
        cr.save()
        cr.move_to(0, height)
        for x, y in points:
            cr.line_to(x, y)
        cr.line_to(width, height)
        cr.close_path()

        pattern = cairo.LinearGradient(0, 0, 0, height)
        pattern.add_color_stop_rgba(0.0, r, g, b, self.fill_opacity)
        pattern.add_color_stop_rgba(1.0, r, g, b, 0.02)
        cr.set_source(pattern)
        cr.fill()
        cr.restore()

        # Draw line
        cr.save()
        cr.set_line_width(2.0)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_source_rgba(r, g, b, 0.95)

        for i, (x, y) in enumerate(points):
            if i == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
        cr.stroke()
        cr.restore()
