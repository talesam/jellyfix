#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/windows/mirabel_dialog.py - Fix Mirabel files dialog
#

"""
Dialog for fixing Mirabel subtitle files.

Renames subtitle files with non-standard language codes like:
- .pt-BR.hi.srt → .por.srt
- .br.hi.srt → .por.srt
- .pt-BR.hi.forced.srt → .por.forced.srt
- .br.hi.forced.srt → .por.forced.srt
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Gio
from pathlib import Path
import re
import threading

from ...utils.logger import get_logger
from ...utils.i18n import _
from ...core.renamer import RenameOperation


class MirabelDialog(Adw.Window):
    """Fix Mirabel files dialog"""

    def __init__(self, parent):
        """
        Initialize Mirabel dialog.

        Args:
            parent: Parent window
        """
        super().__init__(transient_for=parent, modal=True)

        self.logger = get_logger()
        self.parent_window = parent
        self.operations = []
        self.selected_directory = None

        # Pattern to match Mirabel files
        self.mirabel_pattern = re.compile(
            r'^(.+?)\.(pt-BR|pt-br|br|BR|pt_BR|pt_br)\.hi(\.forced)?\.srt$',
            re.IGNORECASE
        )

        # Window properties
        self.set_title(_("Fix Mirabel files"))
        self.set_default_size(700, 600)

        # Build UI
        self._build_ui()

    def _build_ui(self):
        """Build dialog UI"""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Toast overlay
        self.toast_overlay = Adw.ToastOverlay()

        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.set_margin_top(24)
        content_box.set_margin_bottom(24)
        content_box.set_margin_start(24)
        content_box.set_margin_end(24)
        content_box.set_spacing(16)

        # Info banner
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.set_spacing(8)
        info_box.add_css_class("card")
        info_box.set_margin_bottom(8)

        info_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_content.set_margin_top(16)
        info_content.set_margin_bottom(16)
        info_content.set_margin_start(16)
        info_content.set_margin_end(16)
        info_content.set_spacing(8)

        info_title = Gtk.Label()
        info_title.set_markup("<b>" + _("What are Mirabel files?") + "</b>")
        info_title.set_halign(Gtk.Align.START)
        info_content.append(info_title)

        info_text = Gtk.Label()
        info_text.set_markup(_(
            "Subtitle files with non-standard language codes like:\n"
            "• <tt>.pt-BR.hi.srt</tt> → <tt>.por.srt</tt>\n"
            "• <tt>.br.hi.srt</tt> → <tt>.por.srt</tt>\n"
            "• <tt>.pt-BR.hi.forced.srt</tt> → <tt>.por.forced.srt</tt>"
        ))
        info_text.set_halign(Gtk.Align.START)
        info_text.set_wrap(True)
        info_content.append(info_text)

        info_box.append(info_content)
        content_box.append(info_box)

        # Directory selection
        dir_group = Adw.PreferencesGroup(
            title=_("Select Directory")
        )

        self.dir_row = Adw.ActionRow(
            title=_("Directory to scan"),
            subtitle=_("No directory selected")
        )
        self.dir_row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))

        select_button = Gtk.Button(
            label=_("Select"),
            valign=Gtk.Align.CENTER
        )
        select_button.add_css_class("suggested-action")
        select_button.connect("clicked", self._on_select_directory)
        self.dir_row.add_suffix(select_button)
        dir_group.add(self.dir_row)

        content_box.append(dir_group)

        # Results group (initially hidden)
        self.results_group = Adw.PreferencesGroup(
            title=_("Files Found")
        )
        self.results_group.set_visible(False)

        # Scrolled window for file list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(200)
        scrolled.set_max_content_height(300)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.files_list = Gtk.ListBox()
        self.files_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.files_list.add_css_class("boxed-list")
        scrolled.set_child(self.files_list)

        self.results_group.add(scrolled)
        content_box.append(self.results_group)

        # Action buttons box
        self.action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.action_box.set_halign(Gtk.Align.END)
        self.action_box.set_spacing(12)
        self.action_box.set_margin_top(16)
        self.action_box.set_visible(False)

        self.scan_button = Gtk.Button(label=_("Scan"))
        self.scan_button.connect("clicked", self._on_scan)
        self.action_box.append(self.scan_button)

        self.apply_button = Gtk.Button(label=_("Apply Changes"))
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.set_sensitive(False)
        self.apply_button.connect("clicked", self._on_apply)
        self.action_box.append(self.apply_button)

        content_box.append(self.action_box)

        self.toast_overlay.set_child(content_box)
        main_box.append(self.toast_overlay)

        # Set content
        self.set_content(main_box)

    def _on_select_directory(self, button):
        """Handle directory selection"""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select Directory"))

        # Set initial folder to home
        initial_folder = Gio.File.new_for_path(str(Path.home()))
        dialog.set_initial_folder(initial_folder)

        dialog.select_folder(self, None, self._on_directory_selected)

    def _on_directory_selected(self, dialog, result):
        """Handle directory selection result"""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self.selected_directory = Path(folder.get_path())
                self.dir_row.set_subtitle(str(self.selected_directory))
                self.action_box.set_visible(True)
                self.logger.info(f"Selected directory: {self.selected_directory}")
        except Exception as e:
            if "Dismissed" not in str(e):
                self.logger.error(f"Error selecting directory: {e}")

    def _on_scan(self, button):
        """Handle scan button click"""
        if not self.selected_directory:
            return

        # Clear previous results
        while True:
            row = self.files_list.get_first_child()
            if row is None:
                break
            self.files_list.remove(row)

        self.operations = []

        # Show scanning toast
        toast = Adw.Toast(title=_("Scanning for Mirabel files..."))
        toast.set_timeout(0)
        self.toast_overlay.add_toast(toast)

        # Scan in background thread
        def scan_task():
            mirabel_files = []
            for file_path in self.selected_directory.rglob('*.srt'):
                if not file_path.is_file():
                    continue
                if self.mirabel_pattern.match(file_path.name):
                    mirabel_files.append(file_path)

            # Create operations
            operations = []
            for file_path in mirabel_files:
                match = self.mirabel_pattern.match(file_path.name)
                if match:
                    base_name = match.group(1)
                    forced = match.group(3)  # '.forced' or None

                    # Build new filename
                    if forced:
                        new_name = f"{base_name}.por.forced.srt"
                    else:
                        new_name = f"{base_name}.por.srt"

                    new_path = file_path.parent / new_name

                    # Check if destination already exists
                    if new_path.exists() and new_path != file_path:
                        operations.append(RenameOperation(
                            source=file_path,
                            destination=file_path,
                            operation_type='delete',
                            reason=_("Duplicate: %s already exists") % new_name
                        ))
                    else:
                        operations.append(RenameOperation(
                            source=file_path,
                            destination=new_path,
                            operation_type='rename',
                            reason=_("Mirabel fix")
                        ))

            # Update UI on main thread
            GLib.idle_add(self._update_results, operations, toast)

        thread = threading.Thread(target=scan_task, daemon=True)
        thread.start()

    def _update_results(self, operations, toast):
        """Update results on main thread"""
        toast.dismiss()
        self.operations = operations

        if not operations:
            self.results_group.set_visible(False)
            self.apply_button.set_sensitive(False)
            toast = Adw.Toast(title=_("No Mirabel files found"))
            self.toast_overlay.add_toast(toast)
            return

        # Show results
        self.results_group.set_visible(True)
        self.apply_button.set_sensitive(True)

        for op in operations:
            row = Adw.ActionRow()

            if op.operation_type == 'delete':
                row.set_title(op.source.name)
                row.set_subtitle(_("Will be deleted (duplicate)"))
                row.add_prefix(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
                row.add_css_class("error")
            else:
                row.set_title(op.source.name)
                row.set_subtitle(f"→ {op.destination.name}")
                row.add_prefix(Gtk.Image.new_from_icon_name("emblem-ok-symbolic"))

            self.files_list.append(row)

        # Update group title
        self.results_group.set_title(_("Files Found") + f" ({len(operations)})")

        toast = Adw.Toast(title=_("Found {} Mirabel files").format(len(operations)))
        self.toast_overlay.add_toast(toast)

        return False

    def _on_apply(self, button):
        """Handle apply button click"""
        if not self.operations:
            return

        # Confirmation dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Apply Changes?"),
            body=_("This will rename {} files. Continue?").format(len(self.operations))
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("apply", _("Apply"))
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "apply":
                self._execute_operations()

        dialog.connect("response", on_response)
        dialog.present()

    def _execute_operations(self):
        """Execute the rename operations"""
        stats = {'renamed': 0, 'deleted': 0, 'failed': 0}

        for op in self.operations:
            try:
                if op.operation_type == 'delete':
                    op.source.unlink()
                    stats['deleted'] += 1
                else:
                    op.source.rename(op.destination)
                    stats['renamed'] += 1
            except Exception as e:
                self.logger.error(f"Error processing {op.source.name}: {e}")
                stats['failed'] += 1

        # Show results
        msg_parts = []
        if stats['renamed'] > 0:
            msg_parts.append(_("{} renamed").format(stats['renamed']))
        if stats['deleted'] > 0:
            msg_parts.append(_("{} deleted").format(stats['deleted']))
        if stats['failed'] > 0:
            msg_parts.append(_("{} failed").format(stats['failed']))

        toast = Adw.Toast(title=", ".join(msg_parts))
        toast.set_timeout(5)
        self.toast_overlay.add_toast(toast)

        # Clear results and disable apply
        while True:
            row = self.files_list.get_first_child()
            if row is None:
                break
            self.files_list.remove(row)

        self.operations = []
        self.results_group.set_visible(False)
        self.apply_button.set_sensitive(False)

        self.logger.success(_("Mirabel files fixed!"))
