#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/widgets/operations_list.py - Operations list view
#

"""
Operations list view for displaying rename operations.

Shows:
  - Source filename
  - Destination filename
  - Operation type (rename, move, delete)
  - Reason for operation
  - Checkbox for selection
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio
from pathlib import Path
from typing import Optional, Callable, List

from ...utils.i18n import _
from ...core.renamer import RenameOperation


class OperationRow(Adw.ActionRow):
    """Single operation row"""

    def __init__(self, operation: RenameOperation, index: int):
        """
        Initialize operation row.

        Args:
            operation: RenameOperation instance
            index: Operation index
        """
        super().__init__()

        self.operation = operation
        self.index = index

        # Set title to source filename
        self.set_title(operation.source.name)

        # Set subtitle to destination
        dest_name = operation.destination.name
        if operation.source.parent != operation.destination.parent:
            # Different folder, show relative path
            dest_name = f"{operation.destination.parent.name}/{dest_name}"

        self.set_subtitle(f"→ {dest_name}")

        # Add prefix icon based on operation type
        icon_name = {
            'rename': 'document-edit-symbolic',
            'move': 'folder-move-symbolic',
            'delete': 'user-trash-symbolic'
        }.get(operation.operation_type, 'document-edit-symbolic')

        prefix_icon = Gtk.Image.new_from_icon_name(icon_name)
        self.add_prefix(prefix_icon)

        # Add badge for operation type
        if operation.operation_type == 'delete':
            self.add_css_class('error')
        elif operation.will_overwrite:
            self.add_css_class('warning')

        # Make row activatable
        self.set_activatable(True)


class OperationsListView(Gtk.Box):
    """Operations list view widget"""

    def __init__(self, on_operation_selected: Optional[Callable] = None,
                 on_apply_clicked: Optional[Callable] = None):
        """
        Initialize operations list.

        Args:
            on_operation_selected: Callback when operation is selected
            on_apply_clicked: Callback when apply button is clicked
        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.on_operation_selected = on_operation_selected
        self.on_apply_clicked = on_apply_clicked
        self.operations: List[RenameOperation] = []
        self.filtered_operations: List[RenameOperation] = []
        self.current_filter = "all"  # all, rename, move, delete
        self.search_text = ""

        # Set expansion - CRITICAL for layout
        self.set_vexpand(True)
        self.set_hexpand(True)

        # Add CSS class
        self.add_css_class("operations-list")

        # Build UI
        self._build_ui()

    def _build_ui(self):
        """Build operations list UI"""
        # Header bar
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<b>" + _("Operations") + "</b>")
        header.set_title_widget(title_label)

        self.append(header)

        # Toolbar with search and filters
        toolbar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        toolbar.set_spacing(6)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        # Search entry
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search operations..."))
        self.search_entry.connect("search-changed", self._on_search_changed)
        toolbar.append(self.search_entry)

        # Filter buttons
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        filter_box.set_spacing(6)
        filter_box.set_homogeneous(True)

        # All button
        self.filter_all_btn = Gtk.ToggleButton(label=_("All"))
        self.filter_all_btn.set_active(True)
        self.filter_all_btn.connect("toggled", self._on_filter_changed, "all")
        filter_box.append(self.filter_all_btn)

        # Rename button
        self.filter_rename_btn = Gtk.ToggleButton(label=_("Rename"))
        self.filter_rename_btn.set_group(self.filter_all_btn)
        self.filter_rename_btn.connect("toggled", self._on_filter_changed, "rename")
        filter_box.append(self.filter_rename_btn)

        # Move button
        self.filter_move_btn = Gtk.ToggleButton(label=_("Move"))
        self.filter_move_btn.set_group(self.filter_all_btn)
        self.filter_move_btn.connect("toggled", self._on_filter_changed, "move")
        filter_box.append(self.filter_move_btn)

        # Delete button
        self.filter_delete_btn = Gtk.ToggleButton(label=_("Delete"))
        self.filter_delete_btn.set_group(self.filter_all_btn)
        self.filter_delete_btn.connect("toggled", self._on_filter_changed, "delete")
        filter_box.append(self.filter_delete_btn)

        toolbar.append(filter_box)
        self.append(toolbar)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Operations list container
        self.operations_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.operations_box.set_spacing(0)

        # Empty state
        self.empty_state = Adw.StatusPage(
            icon_name="document-properties-symbolic",
            title=_("No Operations"),
            description=_("Scan a directory to generate operations")
        )
        self.operations_box.append(self.empty_state)

        # Operations group (hidden initially)
        self.operations_group = Adw.PreferencesGroup()
        self.operations_group.set_visible(False)

        self.operations_box.append(self.operations_group)

        scrolled.set_child(self.operations_box)
        self.append(scrolled)

        # Status bar with apply button
        self.status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.status_bar.set_spacing(12)
        self.status_bar.set_margin_top(6)
        self.status_bar.set_margin_bottom(6)
        self.status_bar.set_margin_start(12)
        self.status_bar.set_margin_end(12)

        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_hexpand(True)
        self.status_bar.append(self.status_label)

        # Apply button
        self.apply_button = Gtk.Button()
        apply_content = Adw.ButtonContent()
        apply_content.set_icon_name("emblem-ok-symbolic")
        apply_content.set_label(_("Apply"))
        self.apply_button.set_child(apply_content)
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.set_sensitive(False)
        self.apply_button.connect("clicked", self._on_apply_clicked)
        self.status_bar.append(self.apply_button)

        self.append(self.status_bar)

    def _on_apply_clicked(self, button):
        """Handle apply button click"""
        if self.on_apply_clicked and self.operations:
            self.on_apply_clicked(self.operations)

    def set_operations(self, operations: List[RenameOperation]):
        """
        Set operations to display.

        Args:
            operations: List of RenameOperation instances
        """
        self.operations = operations
        self._apply_filters()

        # Enable/disable apply button
        self.apply_button.set_sensitive(len(operations) > 0)

    def _apply_filters(self):
        """Apply current filters and search to operations"""
        # Start with all operations
        filtered = self.operations

        # Apply type filter
        if self.current_filter != "all":
            filtered = [op for op in filtered if op.operation_type == self.current_filter]

        # Apply search filter
        if self.search_text:
            search_lower = self.search_text.lower()
            filtered = [
                op for op in filtered
                if search_lower in op.source.name.lower()
                or search_lower in op.destination.name.lower()
            ]

        self.filtered_operations = filtered
        self._update_display()

    def _update_display(self):
        """Update the display with filtered operations"""
        operations = self.filtered_operations

        # Clear existing rows - rebuild the group instead of removing children
        # Remove old group from operations_box
        self.operations_box.remove(self.operations_group)

        # Create new operations group
        self.operations_group = Adw.PreferencesGroup()
        self.operations_group.set_visible(False)

        # Add new group to box
        self.operations_box.append(self.operations_group)

        if not operations:
            # Show empty state
            self.empty_state.set_visible(True)
            self.operations_group.set_visible(False)
            self.status_label.set_text("")
            return

        # Hide empty state, show operations
        self.empty_state.set_visible(False)
        self.operations_group.set_visible(True)

        # Add operation rows
        for i, operation in enumerate(operations):
            row = OperationRow(operation, i)

            # Connect activation signal
            row.connect("activated", self._on_row_activated)

            self.operations_group.add(row)

        # Update status
        total_ops = len(self.operations)
        shown_ops = len(operations)

        rename_count = sum(1 for op in operations if op.operation_type == 'rename')
        move_count = sum(1 for op in operations if op.operation_type == 'move')
        delete_count = sum(1 for op in operations if op.operation_type == 'delete')

        status_parts = []
        if rename_count:
            status_parts.append(f"{rename_count} " + _("rename"))
        if move_count:
            status_parts.append(f"{move_count} " + _("move"))
        if delete_count:
            status_parts.append(f"{delete_count} " + _("delete"))

        if shown_ops < total_ops:
            status_text = _("Showing {} of {} operations").format(shown_ops, total_ops)
        else:
            status_text = _("Total: {} operations").format(total_ops)

        if status_parts:
            status_text += f" ({', '.join(status_parts)})"

        self.status_label.set_text(status_text)

    def _on_row_activated(self, row: OperationRow):
        """
        Handle row activation.

        Args:
            row: Activated row
        """
        if self.on_operation_selected:
            self.on_operation_selected(row.operation, row.index)

    def _on_search_changed(self, entry: Gtk.SearchEntry):
        """
        Handle search text change.

        Args:
            entry: Search entry widget
        """
        self.search_text = entry.get_text()
        self._apply_filters()

    def _on_filter_changed(self, button: Gtk.ToggleButton, filter_type: str):
        """
        Handle filter button toggle.

        Args:
            button: Toggle button
            filter_type: Filter type (all, rename, move, delete)
        """
        if button.get_active():
            self.current_filter = filter_type
            self._apply_filters()

    def clear(self):
        """Clear all operations"""
        self.set_operations([])
