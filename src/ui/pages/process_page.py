"""
Process Manager page inspired by Windows 11 Task Manager.
Features structured column headers, clickable CPU/RAM/PID/Name/User sorting with visual indicators,
responsive adaptive layout for Hyprland window tiling, and a detailed process inspection panel.
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Pango, GLib
import signal
from typing import Dict, List, Optional
from ...collectors.process import ProcessCollector

class ProcessPage(Gtk.Box):
    def __init__(self, toast_overlay: Adw.ToastOverlay):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.toast_overlay = toast_overlay
        self.set_vexpand(True)
        self.set_hexpand(True)

        # Padding adapts responsively
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(14)
        self.set_margin_bottom(14)

        self.raw_processes: List[dict] = []
        self.filtered_processes: List[dict] = []
        self.selected_pid: Optional[int] = None
        self.selected_proc_data: Optional[dict] = None

        # Sorting state: default is highest CPU first
        self.sort_key: str = "cpu_percent"
        self.sort_descending: bool = True
        self.layout_mode: str = "wide" # "wide", "medium", "compact"
        self.show_details: bool = True

        # Header Title
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="Processes")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")

        self.summary_label = Gtk.Label(label="Scanning active system tasks...")
        self.summary_label.set_halign(Gtk.Align.START)
        self.summary_label.add_css_class("dim-label")
        self.summary_label.add_css_class("caption")

        title_box.append(title)
        title_box.append(self.summary_label)
        self.append(title_box)

        # Action Bar (Search + Details Toggle + End Process)
        action_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        action_bar.set_margin_top(4)
        action_bar.set_margin_bottom(4)

        # Search Entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search processes by name or PID...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        action_bar.append(self.search_entry)

        # Toggle Details Panel Button
        self.details_toggle_btn = Gtk.Button()
        self.details_toggle_btn.set_icon_name("view-reveal-symbolic")
        self.details_toggle_btn.set_tooltip_text("Toggle Process Details Panel")
        self.details_toggle_btn.add_css_class("flat")
        self.details_toggle_btn.connect("clicked", self._on_toggle_details_clicked)
        action_bar.append(self.details_toggle_btn)

        # End Process Button
        self.end_btn = Gtk.Button(label="End Process")
        self.end_btn.add_css_class("destructive-action")
        self.end_btn.set_sensitive(False)
        self.end_btn.connect("clicked", self._on_end_process_clicked)
        action_bar.append(self.end_btn)

        self.append(action_bar)

        # Main Split Container: Process Table + Process Details Panel
        self.split_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.split_box.set_vexpand(True)
        self.split_box.set_hexpand(True)

        # --- Table Container (Header + Listbox) ---
        self.table_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.table_container.set_hexpand(True)
        self.table_container.set_vexpand(True)

        # Column Header Row (Clickable buttons with sorting arrows)
        self.header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.header_row.add_css_class("card")
        self.header_row.set_margin_bottom(2)

        # 1. Process Name Header
        self.btn_col_name = self._create_header_button("Process", "name", Gtk.Align.START, hexpand=True, min_width=150)
        self.header_row.append(self.btn_col_name)

        # 2. Memory (RAM) Header
        self.btn_col_mem = self._create_header_button("Memory (RAM)", "memory_bytes", Gtk.Align.END, width=135)
        self.header_row.append(self.btn_col_mem)

        # 3. CPU Usage Header (Default Sorted Descending)
        self.btn_col_cpu = self._create_header_button("CPU Usage ▼", "cpu_percent", Gtk.Align.END, width=95)
        self.header_row.append(self.btn_col_cpu)

        # 4. Status Header
        self.btn_col_status = self._create_header_button("Status", "state", Gtk.Align.START, width=75)
        self.header_row.append(self.btn_col_status)

        # 5. PID Header
        self.btn_col_pid = self._create_header_button("PID", "pid", Gtk.Align.END, width=65)
        self.header_row.append(self.btn_col_pid)

        # 6. User Header
        self.btn_col_user = self._create_header_button("User", "user", Gtk.Align.START, width=80)
        self.header_row.append(self.btn_col_user)

        self.table_container.append(self.header_row)

        # Process List (Scrolled)
        self.list_scroll = Gtk.ScrolledWindow()
        self.list_scroll.set_hexpand(True)
        self.list_scroll.set_vexpand(True)
        self.list_scroll.add_css_class("card")

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self._on_row_selected)
        self.list_scroll.set_child(self.listbox)
        self.table_container.append(self.list_scroll)

        self.split_box.append(self.table_container)

        # --- Process Details Panel ---
        self.detail_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.detail_card.add_css_class("card")
        self.detail_card.set_size_request(300, -1)
        self.detail_card.set_margin_start(2)
        self.detail_card.set_margin_end(2)

        # Detail Panel Header
        d_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        d_top.set_margin_start(14)
        d_top.set_margin_end(14)
        d_top.set_margin_top(12)

        self.d_title = Gtk.Label(label="Process Details")
        self.d_title.set_halign(Gtk.Align.START)
        self.d_title.set_hexpand(True)
        self.d_title.add_css_class("title-3")
        d_top.append(self.d_title)

        self.d_pid_badge = Gtk.Label(label="")
        self.d_pid_badge.set_halign(Gtk.Align.END)
        self.d_pid_badge.add_css_class("caption")
        self.d_pid_badge.add_css_class("dim-label")
        d_top.append(self.d_pid_badge)
        self.detail_card.append(d_top)

        # Scrolled container for detail items so long command lines never overflow
        detail_scroll = Gtk.ScrolledWindow()
        detail_scroll.set_vexpand(True)
        detail_scroll.set_hexpand(True)

        detail_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        detail_content.set_margin_start(14)
        detail_content.set_margin_end(14)
        detail_content.set_margin_top(8)
        detail_content.set_margin_bottom(12)

        self.d_stat_name = self._create_detail_row("Process Name", "--")
        self.d_stat_mem = self._create_detail_row("Resident Memory (RAM)", "--")
        self.d_stat_cpu = self._create_detail_row("CPU Utilization", "--")
        self.d_stat_state = self._create_detail_row("Process State", "--")
        self.d_stat_pid = self._create_detail_row("PID / Parent PID", "--")
        self.d_stat_user = self._create_detail_row("User (UID)", "--")
        self.d_stat_runtime = self._create_detail_row("Elapsed Runtime", "--")
        self.d_stat_exe = self._create_detail_row("Executable Path", "--")

        detail_content.append(self.d_stat_name["box"])
        detail_content.append(self.d_stat_mem["box"])
        detail_content.append(self.d_stat_cpu["box"])
        detail_content.append(self.d_stat_state["box"])
        detail_content.append(self.d_stat_pid["box"])
        detail_content.append(self.d_stat_user["box"])
        detail_content.append(self.d_stat_runtime["box"])
        detail_content.append(self.d_stat_exe["box"])

        # Command Line Section
        cmd_lbl = Gtk.Label(label="Command Line:")
        cmd_lbl.set_halign(Gtk.Align.START)
        cmd_lbl.add_css_class("caption")
        cmd_lbl.add_css_class("dim-label")
        cmd_lbl.set_margin_top(6)
        detail_content.append(cmd_lbl)

        self.d_cmdline = Gtk.Label(label="Select a running process to view command line and detailed statistics.")
        self.d_cmdline.set_wrap(True)
        self.d_cmdline.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.d_cmdline.set_selectable(True)
        self.d_cmdline.set_halign(Gtk.Align.START)
        self.d_cmdline.add_css_class("caption")
        detail_content.append(self.d_cmdline)

        detail_scroll.set_child(detail_content)
        self.detail_card.append(detail_scroll)

        self.split_box.append(self.detail_card)
        self.append(self.split_box)

    def _create_header_button(self, label_text: str, sort_field: str, halign: Gtk.Align, 
                             hexpand: bool = False, min_width: Optional[int] = None, width: Optional[int] = None) -> Gtk.Button:
        btn = Gtk.Button()
        btn.add_css_class("flat")
        btn.sort_field = sort_field
        btn.base_title = label_text.replace(" ▼", "").replace(" ▲", "")

        lbl = Gtk.Label(label=label_text)
        lbl.set_halign(halign)
        lbl.add_css_class("heading")
        lbl.add_css_class("caption")

        btn.set_child(lbl)
        btn.label_widget = lbl

        if hexpand:
            btn.set_hexpand(True)
        if min_width:
            btn.set_size_request(min_width, -1)
        elif width:
            btn.set_size_request(width, -1)

        btn.connect("clicked", lambda b: self._on_header_clicked(sort_field))
        return btn

    def _create_detail_row(self, title: str, val: str) -> dict:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        t_lbl = Gtk.Label(label=title)
        t_lbl.set_halign(Gtk.Align.START)
        t_lbl.add_css_class("caption")
        t_lbl.add_css_class("dim-label")

        v_lbl = Gtk.Label(label=val)
        v_lbl.set_halign(Gtk.Align.START)
        v_lbl.set_selectable(True)
        v_lbl.set_wrap(True)
        v_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        v_lbl.add_css_class("caption")
        v_lbl.add_css_class("heading")

        box.append(t_lbl)
        box.append(v_lbl)
        return {"box": box, "title": t_lbl, "value": v_lbl}

    def _on_header_clicked(self, field: str):
        if self.sort_key == field:
            # Toggle direction
            self.sort_descending = not self.sort_descending
        else:
            self.sort_key = field
            # Numeric fields default to highest first; textual fields default to ascending
            if field in ("cpu_percent", "memory_bytes"):
                self.sort_descending = True
            else:
                self.sort_descending = False

        self._update_header_arrows()
        self._filter_and_sort()
        self._render_rows()

    def _update_header_arrows(self):
        arrow = " ▼" if self.sort_descending else " ▲"
        headers = [
            (self.btn_col_name, "name"),
            (self.btn_col_mem, "memory_bytes"),
            (self.btn_col_cpu, "cpu_percent"),
            (self.btn_col_status, "state"),
            (self.btn_col_pid, "pid"),
            (self.btn_col_user, "user"),
        ]

        for btn, field in headers:
            base = btn.base_title
            if self.sort_key == field:
                btn.label_widget.set_label(f"{base}{arrow}")
                btn.add_css_class("accent")
            else:
                btn.label_widget.set_label(base)
                btn.remove_css_class("accent")

    def _on_toggle_details_clicked(self, btn):
        self.show_details = not self.show_details
        self.detail_card.set_visible(self.show_details)

    def set_responsive_layout(self, width: int):
        """Adapt layout dynamically based on actual window width for Hyprland split/tiling."""
        if width >= 1150:
            new_mode = "wide"
        elif width >= 800:
            new_mode = "medium"
        else:
            new_mode = "compact"

        if new_mode == self.layout_mode:
            return

        self.layout_mode = new_mode

        if new_mode == "wide":
            # Three-part wide layout: Table and Details Panel side-by-side
            self.split_box.set_orientation(Gtk.Orientation.HORIZONTAL)
            self.detail_card.set_size_request(300, -1)
            self.detail_card.set_visible(self.show_details)
            self.btn_col_user.set_visible(True)
            self.btn_col_status.set_visible(True)
            self.set_margin_start(16)
            self.set_margin_end(16)

        elif new_mode == "medium":
            # Medium layout: Details panel moves below table to give table full width
            self.split_box.set_orientation(Gtk.Orientation.VERTICAL)
            self.detail_card.set_size_request(-1, 180)
            self.detail_card.set_visible(self.show_details)
            self.btn_col_user.set_visible(True)
            self.btn_col_status.set_visible(True)
            self.set_margin_start(12)
            self.set_margin_end(12)

        else: # compact (<800px, e.g. tiled split or small window)
            # Compact layout: hide non-essential columns (User, Status) to prevent squeeze
            self.split_box.set_orientation(Gtk.Orientation.VERTICAL)
            self.detail_card.set_size_request(-1, 160)
            self.detail_card.set_visible(self.show_details and self.selected_pid is not None)
            self.btn_col_user.set_visible(False)
            self.btn_col_status.set_visible(False)
            self.set_margin_start(8)
            self.set_margin_end(8)

        # Re-render rows to adapt column visibility
        self._render_rows()

    def _on_search_changed(self, entry):
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

        # Proper numeric and textual sorting across the complete filtered dataset
        def sort_accessor(item):
            val = item.get(self.sort_key)
            if val is None:
                return 0 if self.sort_key in ("cpu_percent", "memory_bytes", "pid", "runtime_sec") else ""
            if isinstance(val, str):
                return val.lower()
            return val

        self.filtered_processes.sort(key=sort_accessor, reverse=self.sort_descending)

    def _format_memory(self, b: int) -> str:
        mib = b / (1024 * 1024)
        if mib >= 1024:
            return f"{mib / 1024:.2f} GiB"
        return f"{mib:.1f} MiB"

    def _format_runtime(self, sec: int) -> str:
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        if h > 0:
            return f"{h}h {m}m {s}s"
        return f"{m}m {s}s"

    def update_metrics(self, data: dict):
        proc_data = data.get("process", {})
        self.raw_processes = proc_data.get("processes", [])
        self.summary_label.set_label(f"{len(self.raw_processes)} tasks running • Click column headers to sort")

        self._filter_and_sort()
        self._render_rows()

        # Update details panel if a process is currently selected
        if self.selected_pid:
            updated_p = next((p for p in self.raw_processes if p["pid"] == self.selected_pid), None)
            if updated_p:
                self.selected_proc_data = updated_p
                self._update_details_panel(updated_p)
            else:
                self.d_title.set_label(f"Process {self.selected_pid} exited")
                self.d_pid_badge.set_label("TERMINATED")
                self.end_btn.set_sensitive(False)

    def _render_rows(self):
        # Clear existing rows
        while True:
            row = self.listbox.get_row_at_index(0)
            if row is None:
                break
            self.listbox.remove(row)

        target_row_to_select = None

        # Display top 100 matching processes for responsiveness
        for p in self.filtered_processes[:100]:
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_box.set_margin_start(8)
            row_box.set_margin_end(8)
            row_box.set_margin_top(4)
            row_box.set_margin_bottom(4)

            # 1. Process Name (Prominent, hexpand=True, min width 150)
            name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            name_box.set_hexpand(True)
            name_box.set_size_request(150, -1)
            name_box.set_halign(Gtk.Align.START)

            name_lbl = Gtk.Label(label=p["name"])
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            name_lbl.add_css_class("heading")
            name_box.append(name_lbl)
            row_box.append(name_box)

            # 2. Memory (RAM) Column (width 135, right aligned, with units and %)
            mem_formatted = self._format_memory(p["memory_bytes"])
            mem_pct = p["memory_percent"]
            mem_lbl = Gtk.Label(label=f"{mem_formatted} ({mem_pct:.1f}%)")
            mem_lbl.set_size_request(135, -1)
            mem_lbl.set_halign(Gtk.Align.END)
            mem_lbl.add_css_class("caption")
            mem_lbl.add_css_class("dim-label")
            row_box.append(mem_lbl)

            # 3. CPU Usage Column (width 95, right aligned, with % symbol)
            cpu_val = p["cpu_percent"]
            cpu_lbl = Gtk.Label(label=f"{cpu_val:.1f}%")
            cpu_lbl.set_size_request(95, -1)
            cpu_lbl.set_halign(Gtk.Align.END)
            cpu_lbl.add_css_class("caption")
            cpu_lbl.add_css_class("heading")
            if cpu_val >= 20.0:
                cpu_lbl.add_css_class("accent")
            row_box.append(cpu_lbl)

            # 4. Status Column (width 75, start aligned, hidden in compact mode)
            status_lbl = Gtk.Label(label=p["state"])
            status_lbl.set_size_request(75, -1)
            status_lbl.set_halign(Gtk.Align.START)
            status_lbl.add_css_class("caption")
            if p["state"] == "Running":
                status_lbl.add_css_class("accent")
            else:
                status_lbl.add_css_class("dim-label")
            status_lbl.set_visible(self.layout_mode != "compact")
            row_box.append(status_lbl)

            # 5. PID Column (width 65, right aligned)
            pid_lbl = Gtk.Label(label=str(p["pid"]))
            pid_lbl.set_size_request(65, -1)
            pid_lbl.set_halign(Gtk.Align.END)
            pid_lbl.add_css_class("caption")
            pid_lbl.add_css_class("dim-label")
            row_box.append(pid_lbl)

            # 6. User Column (width 80, start aligned, hidden in compact mode)
            user_lbl = Gtk.Label(label=p["user"])
            user_lbl.set_size_request(80, -1)
            user_lbl.set_halign(Gtk.Align.START)
            user_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            user_lbl.add_css_class("caption")
            user_lbl.add_css_class("dim-label")
            user_lbl.set_visible(self.layout_mode != "compact")
            row_box.append(user_lbl)

            row.set_child(row_box)
            row.pid = p["pid"]
            row.proc_data = p
            self.listbox.append(row)

            if self.selected_pid == p["pid"]:
                target_row_to_select = row

        if target_row_to_select:
            self.listbox.select_row(target_row_to_select)

    def _on_row_selected(self, listbox, row):
        if row:
            p = getattr(row, "proc_data", None)
            if p:
                self.selected_pid = p["pid"]
                self.selected_proc_data = p
                self.end_btn.set_sensitive(True)
                self._update_details_panel(p)
                if self.layout_mode == "compact":
                    self.detail_card.set_visible(True)
                return

        self.selected_pid = None
        self.selected_proc_data = None
        self.end_btn.set_sensitive(False)
        self.d_title.set_label("Process Details")
        self.d_pid_badge.set_label("")
        self.d_cmdline.set_label("Select a running process to view command line and detailed statistics.")

    def _update_details_panel(self, p: dict):
        self.d_title.set_label(p["name"])
        self.d_pid_badge.set_label(f"PID: {p['pid']}")

        self.d_stat_name["value"].set_label(p["name"])
        self.d_stat_pid["value"].set_label(f"{p['pid']} (PPID: {p['ppid']})")
        self.d_stat_user["value"].set_label(f"{p['user']} (UID: {p['uid']})")
        self.d_stat_state["value"].set_label(p["state"])
        self.d_stat_cpu["value"].set_label(f"{p['cpu_percent']}% Utilization")

        mem_str = self._format_memory(p["memory_bytes"])
        self.d_stat_mem["value"].set_label(f"{mem_str} ({p['memory_percent']}% of Physical RAM)")

        runtime_str = self._format_runtime(p["runtime_sec"])
        self.d_stat_runtime["value"].set_label(runtime_str)

        exe_path = p.get("exe_path", "--")
        self.d_stat_exe["value"].set_label(exe_path or "--")

        cmd = p.get("cmdline", p["name"])
        self.d_cmdline.set_label(cmd or "--")

    def _on_end_process_clicked(self, btn):
        if not self.selected_pid or not self.selected_proc_data:
            return

        p = self.selected_proc_data
        p_name = p["name"]
        pid = p["pid"]

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
