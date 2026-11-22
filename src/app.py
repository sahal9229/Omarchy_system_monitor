"""
Main Application entry point for Omarchy System Monitor.
Handles single-instance lifecycle via Adw.Application (GApplication).
"""
import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib

from .config import ConfigManager
from .ui.window import MainWindow

class OmarchySystemMonitorApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="org.omarchy.SystemMonitor",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        self.config_mgr = ConfigManager()
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = MainWindow(self, self.config_mgr)
        self.window.present()

    def do_startup(self):
        Adw.Application.do_startup(self)

def main():
    app = OmarchySystemMonitorApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
