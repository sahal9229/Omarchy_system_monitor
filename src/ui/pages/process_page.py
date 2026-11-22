"""
Process Manager page inspired by Windows 11 Task Manager.
Sortable process list, live search filter, process inspection details,
and confirmation-based process termination (SIGTERM / SIGKILL).
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib
import signal
from typing import Dict, List, Optional
from ...collectors.process import ProcessCollector

class ProcessPage(Gtk.Box):
    def __init__(self, toast_overlay: Adw.ToastOverlay):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.toast_overlay = toast_overlay
        self.set_vexpand(True)
        self.set_hexpand(True)

        self.set_margin_start(24)
        self.set_margin_end(24)
        self.set_margin_top(20)
        self.set_margin_bottom(20)

        self.raw_processes: List[dict] = []
        self.filtered_processes: List[dict] = []
        self.selected_pid: Optional[int] = None
        self.sort_key: str = "cpu_percent"
        self.sort_descending: bool = True

        # Header Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label="Processes")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        self.summary_label = Gtk.Label(label="Running tasks and resource consumption")
        self.summary_label.set_halign(Gtk.Align.START)
        self.summary_label.add_css_class("dim-label")

        title_box.append(title)
        title_box.append(self.summary_label)
        self.append(title_box)

        # Action Bar (Search + Sort + End Process)
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        action_bar.set_margin_top(4)

        # Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search by name or PID...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        action_bar.append(self.search_entry)

        # Sort selector
        sort_label = Gtk.Label(label="Sort:")
        sort_label.add_css_class("dim-label")
        action_bar.append(sort_label)

        self.sort_dropdown = Gtk.DropDown.new_from_strings([
            "CPU % (High to Low)",
            "Memory (High to Low)",
            "PID",
            "Name (A-Z)"
        ])
        self.sort_dropdown.connect("notify::selected", self._on_sort_changed)
        action_bar.append(self.sort_dropdown)

        # End Process Button
        self.end_btn = Gtk.Button(label="End Process")
        self.end_btn.add_css_class("destructive-action")
        self.end_btn.set_sensitive(False)
        self.end_btn.connect("clicked", self._on_end_process_clicked)
        action_bar.append(self.end_btn)

        self.append(action_bar)

        # Split: Process List (Scrolled) and Detail Sidebar
        split_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        split_box.set_vexpand(True)

        # Process Table List
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_hexpand(True)
        list_scroll.set_vexpand(True)
        list_scroll.add_css_class("card")

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self._on_row_selected)
        list_scroll.set_child(self.listbox)
        split_box.append(list_scroll)

        # Process Details Card (Right pane)
        self.detail_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.detail_card.add_css_class("card")
        self.detail_card.set_size_request(280, -1)
        self.detail_card.set_margin_start(4)
        self.detail_card.set_margin_end(4)

        d_header = Gtk.Label(label="Process Details")
        d_header.set_halign(Gtk.Align.START)
        d_header.set_margin_start(12)
        d_header.set_margin_top(12)
        d_header.add_css_class("title-3")
        self.detail_card.append(d_header)

        self.detail_info = Gtk.Label(label="Select a process to inspect details.")
        self.detail_info.set_wrap(True)
        self.detail_info.set_halign(Gtk.Align.START)
        self.detail_info.set_margin_start(12)
        self.detail_info.set_margin_end(12)
        self.detail_info.set_margin_top(8)
        self.detail_info.set_selectable(True)
        self.detail_info.add_css_class("caption")
        self.detail_card.append(self.detail_info)

        split_box.append(self.detail_card)
        self.append(split_box)

    def _on_search_changed(self, entry):
        self._filter_and_sort()
        self._render_rows()

    def _on_sort_changed(self, dropdown, param):
        idx = dropdown.get_selected()
        if idx == 0:
            self.sort_key = "cpu_percent"
            self.sort_descending = True
        elif idx == 1:
            self.sort_key = "memory_bytes"
            self.sort_descending = True
        elif idx == 2:
            self.sort_key = "pid"
            self.sort_descending = False
        elif idx == 3:
            self.sort_key = "name"
            self.sort_descending = False
        self._filter_and_sort()
        self._render_rows()

    def _filter_and_sort(self):
        query = self.search_entry.get_text().strip().lower()
        if query:
            self.filtered_processes = [
                p for p in self.raw_processes
                if query in p["name"].lower() or query == str(p["pid"])
            ]
        else:
            self.filtered_processes = list(self.raw_processes)

        self.filtered_processes.sort(
            key=lambda x: x.get(self.sort_key, 0),
            reverse=self.sort_descending
        )

    def update_metrics(self, data: dict):
        proc_data = data.get("process", {})
        self.raw_processes = proc_data.get("processes", [])
        self.summary_label.set_label(f"{len(self.raw_processes)} Total Tasks Running")

        self._filter_and_sort()
        self._render_rows()

    def _render_rows(self):
        # Clear existing rows
        while True:
            row = self.listbox.get_row_at_index(0)
            if row is None:
                break
            self.listbox.remove(row)

        # Show top 100 for optimal UI rendering performance
        for p in self.filtered_processes[:100]:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_box.set_margin_start(12)
            row_box.set_margin_end(12)
            row_box.set_margin_top(6)
            row_box.set_margin_bottom(6)

            # Name and PID
            name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            name_box.set_hexpand(True)
            name_box.set_halign(Gtk.Align.START)

            name_lbl = Gtk.Label(label=p["name"])
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.add_css_class("heading")

            sub_lbl = Gtk.Label(label=f"PID: {p['pid']} • User: {p['user']} • {p['state']}")
            sub_lbl.set_halign(Gtk.Align.START)
            sub_lbl.add_css_class("caption")
            sub_lbl.add_css_class("dim-label")

            name_box.append(name_lbl)
            name_box.append(sub_lbl)
            row_box.append(name_box)

            # CPU Badge
            cpu_val = p["cpu_percent"]
            cpu_lbl = Gtk.Label(label=f"{cpu_val:.1f}% CPU")
            cpu_lbl.set_size_request(80, -1)
            cpu_lbl.set_halign(Gtk.Align.END)
            if cpu_val >= 20.0:
                cpu_lbl.add_css_class("accent")
            else:
                cpu_lbl.add_css_class("dim-label")
            row_box.append(cpu_lbl)

            # Memory Badge
            mem_mb = p["memory_bytes"] / (1024 * 1024)
            mem_lbl = Gtk.Label(label=f"{mem_mb:.1f} MB")
            mem_lbl.set_size_request(80, -1)
            mem_lbl.set_halign(Gtk.Align.END)
            mem_lbl.add_css_class("dim-label")
            row_box.append(mem_lbl)

            row.set_child(row_box)
            row.pid = p["pid"]
            row.proc_data = p
            self.listbox.append(row)

            # Re-select if it was selected
            if self.selected_pid == p["pid"]:
                self.listbox.select_row(row)

    def _on_row_selected(self, listbox, row):
        if row:
            p = getattr(row, "proc_data", None)
            if p:
                self.selected_pid = p["pid"]
                self.end_btn.set_sensitive(True)

                mem_mb = p["memory_bytes"] / (1024 * 1024)
                runtime_m = p["runtime_sec"] // 60
                runtime_s = p["runtime_sec"] % 60

                details = (
                    f"<b>Process:</b> {p['name']}\n"
                    f"<b>PID:</b> {p['pid']} (PPID: {p['ppid']})\n"
                    f"<b>User:</b> {p['user']} (UID: {p['uid']})\n"
                    f"<b>State:</b> {p['state']}\n"
                    f"<b>CPU Usage:</b> {p['cpu_percent']}%\n"
                    f"<b>Memory (RSS):</b> {mem_mb:.1f} MB ({p['memory_percent']}%)\n"
                    f"<b>Runtime:</b> {runtime_m}m {runtime_s}s\n\n"
                    f"<b>Command:</b>\n{p['cmdline'][:300]}"
                )
                self.detail_info.set_markup(details)
                return

        self.selected_pid = None
        self.end_btn.set_sensitive(False)
        self.detail_info.set_label("Select a process to inspect details.")

    def _on_end_process_clicked(self, btn):
        if not self.selected_pid:
            return

        target_proc = next((p for p in self.raw_processes if p["pid"] == self.selected_pid), None)
        if not target_proc:
            return

        p_name = target_proc["name"]
        pid = target_proc["pid"]

        # Confirmation Dialog
        root_win = self.get_root()
        dialog = Adw.AlertDialog(
            heading=f"End Process '{p_name}'?",
            body=f"Ending process {pid} will terminate it immediately. Default is graceful SIGTERM shutdown."
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("term", "End Process (SIGTERM)")
        dialog.add_response("kill", "Force Kill (SIGKILL)")
        dialog.set_response_appearance("kill", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        def on_response(dlg, response):
            if response in ("term", "kill"):
                sig = signal.SIGKILL if response == "kill" else signal.SIGTERM
                success, msg = ProcessCollector.terminate_process(pid, sig)
                toast = Adw.Toast.new(msg)
                toast.set_timeout(4)
                self.toast_overlay.add_toast(toast)

        dialog.connect("response", on_response)
        dialog.present(root_win)
