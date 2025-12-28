#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/widgets/dashboard.py - Dashboard view with Welcome Screen
#

"""
Dashboard view with intuitive Welcome Screen.

Displays:
  - Drop zone for drag-and-drop folders
  - "Add Library" button
  - Recent libraries history
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gdk, Gio, GLib
from pathlib import Path
from datetime import datetime
from ...utils.i18n import _
from ...utils.config_manager import ConfigManager


class DashboardView(Gtk.Box):
    """Dashboard view widget with Welcome Screen"""

    def __init__(self, on_scan_clicked=None, on_process_clicked=None):
        """
        Initialize dashboard.

        Args:
            on_scan_clicked: Callback for scan action (receives directory path)
            on_process_clicked: Callback for process action
        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        # Store callbacks
        self.on_scan_clicked = on_scan_clicked
        self.on_process_clicked = on_process_clicked
        self.config_manager = ConfigManager()

        # Set expansion
        self.set_vexpand(True)
        self.set_hexpand(True)

        # Add CSS class
        self.add_css_class("dashboard-view")

        # Build UI
        self._build_ui()
        self._setup_drag_drop()

    def _build_ui(self):
        """Build dashboard UI with Welcome Screen"""
        # Main content box
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.set_spacing(24)
        content.set_margin_top(32)
        content.set_margin_bottom(32)
        content.set_margin_start(24)
        content.set_margin_end(24)
        content.set_vexpand(True)
        content.set_valign(Gtk.Align.START)

        # Welcome header
        welcome_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        welcome_box.set_spacing(8)
        welcome_box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("folder-videos-symbolic")
        icon.set_pixel_size(48)
        icon.set_opacity(0.6)
        welcome_box.append(icon)

        title = Gtk.Label()
        title.set_markup("<big><b>" + _("Welcome to Jellyfix") + "</b></big>")
        title.set_margin_top(8)
        welcome_box.append(title)

        content.append(welcome_box)

        # Drop zone frame
        self.drop_zone = Gtk.Frame()
        self.drop_zone.add_css_class("card")
        self.drop_zone.set_margin_top(16)

        drop_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        drop_content.set_spacing(16)
        drop_content.set_margin_top(40)
        drop_content.set_margin_bottom(40)
        drop_content.set_margin_start(32)
        drop_content.set_margin_end(32)
        drop_content.set_halign(Gtk.Align.CENTER)

        # Drop icon
        drop_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        drop_icon.set_pixel_size(64)
        drop_icon.set_opacity(0.4)
        drop_content.append(drop_icon)

        # Drop text
        drop_label = Gtk.Label()
        drop_label.set_markup(
            "<span size='large'>" + _("Drop a folder here") + "</span>\n" +
            "<span size='small' alpha='60%'>" + _("or click the button below") + "</span>"
        )
        drop_label.set_justify(Gtk.Justification.CENTER)
        drop_content.append(drop_label)

        # Add library button
        add_button = Gtk.Button()
        add_button.set_label(_("Add Library"))
        add_button.add_css_class("suggested-action")
        add_button.add_css_class("pill")
        add_button.set_margin_top(8)
        add_button.connect("clicked", self._on_add_library_clicked)

        # Button content with icon
        button_content = Adw.ButtonContent()
        button_content.set_icon_name("folder-new-symbolic")
        button_content.set_label(_("Add Library"))
        add_button.set_child(button_content)

        drop_content.append(add_button)

        self.drop_zone.set_child(drop_content)
        content.append(self.drop_zone)

        # Recent libraries section
        self._build_recent_libraries(content)

        self.append(content)

    def _build_recent_libraries(self, parent):
        """Build recent libraries section"""
        recent_libs = self.config_manager.get_recent_libraries(5)

        if not recent_libs:
            return

        # Recent libraries group
        self.recent_group = Adw.PreferencesGroup(
            title=_("Recent Libraries")
        )
        self.recent_group.set_margin_top(16)

        for lib in recent_libs:
            path = lib.get('path', '')
            timestamp = lib.get('timestamp', '')

            # Format time ago
            time_text = self._format_time_ago(timestamp)

            row = Adw.ActionRow(
                title=Path(path).name,
                subtitle=path,
                activatable=True
            )
            row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))

            # Time label
            time_label = Gtk.Label(label=time_text)
            time_label.add_css_class("dim-label")
            row.add_suffix(time_label)

            row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))

            # Store path for callback
            row.library_path = path
            row.connect("activated", self._on_recent_library_clicked)

            self.recent_group.add(row)

        # Add clear button
        clear_row = Adw.ActionRow(
            title=_("Clear recent libraries"),
            activatable=True
        )
        clear_row.add_prefix(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
        clear_row.add_css_class("destructive-action")
        clear_row.connect("activated", self._on_clear_recent_clicked)
        self.recent_group.add(clear_row)

        parent.append(self.recent_group)

    def _on_clear_recent_clicked(self, row):
        """Handle clear recent libraries click"""
        self.config_manager.clear_recent_libraries()
        self.refresh_recent_libraries()

    def _format_time_ago(self, timestamp_str: str) -> str:
        """Format timestamp as time ago string"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            now = datetime.now()
            diff = now - timestamp

            if diff.days > 7:
                return f"{diff.days // 7} " + _("weeks ago")
            elif diff.days > 0:
                return f"{diff.days} " + _("days ago")
            elif diff.seconds > 3600:
                return f"{diff.seconds // 3600} " + _("hours ago")
            else:
                return _("Just now")
        except Exception:
            return ""

    def _setup_drag_drop(self):
        """Setup drag and drop for folder"""
        # Create drop target for multiple files
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_drop)
        drop_target.connect("enter", self._on_drag_enter)
        drop_target.connect("leave", self._on_drag_leave)

        self.drop_zone.add_controller(drop_target)

    def _on_drag_enter(self, drop_target, x, y):
        """Handle drag enter"""
        self.drop_zone.add_css_class("drop-active")
        return Gdk.DragAction.COPY

    def _on_drag_leave(self, drop_target):
        """Handle drag leave"""
        self.drop_zone.remove_css_class("drop-active")

    def _on_drop(self, drop_target, value, x, y):
        """Handle folder drop - supports multiple folders"""
        self.drop_zone.remove_css_class("drop-active")

        if isinstance(value, Gdk.FileList):
            # Get all files from the list
            files = list(value.get_files())
            directories = []

            for file in files:
                if file:
                    path = Path(file.get_path())
                    if path.is_dir():
                        directories.append(path)

            if len(directories) == 1:
                # Single directory - scan it directly
                self._start_scan(directories[0])
                return True
            elif len(directories) > 1:
                # Multiple directories - find common parent and scan it
                # Or scan each one and merge operations
                self._start_multi_scan(directories)
                return True

        return False

    def _start_multi_scan(self, directories: list):
        """Start scanning multiple directories"""
        # Find common parent directory if possible
        common_parent = directories[0].parent
        all_in_same_parent = all(d.parent == common_parent for d in directories)

        if all_in_same_parent:
            # If all are in the same parent, scan the parent
            self._start_scan(common_parent)
        else:
            # Otherwise, scan each directory sequentially
            # For now, just scan the first one and show a message
            # TODO: Implement proper multi-directory scanning
            self._start_scan(directories[0])

    def _on_add_library_clicked(self, button):
        """Handle add library button click"""
        if self.on_scan_clicked:
            self.on_scan_clicked(button)

    def _on_recent_library_clicked(self, row):
        """Handle recent library click"""
        path = Path(row.library_path)
        if path.exists() and path.is_dir():
            self._start_scan(path)

    def _start_scan(self, directory: Path):
        """Start scanning a directory"""
        # Add to recent libraries
        self.config_manager.add_recent_library(str(directory))

        # Trigger scan callback - we need to simulate the scan flow
        # The main_window will handle this through operations_handler
        if self.on_scan_clicked:
            # Create a fake event and pass directory info
            self.selected_directory = directory
            self.on_scan_clicked(self)

    def refresh_recent_libraries(self):
        """Refresh the recent libraries list"""
        # Remove old recent group if exists
        if hasattr(self, 'recent_group'):
            parent = self.recent_group.get_parent()
            if parent:
                parent.remove(self.recent_group)

        # Rebuild
        content = self.get_first_child()
        if content:
            self._build_recent_libraries(content)
