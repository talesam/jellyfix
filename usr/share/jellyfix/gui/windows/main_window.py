#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/windows/main_window.py - Main application window
#

"""
Main application window with split-view layout.

Layout:
  - Left sidebar: Operations list
  - Right panel: Preview with poster and metadata
  - Header bar with actions
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib
from pathlib import Path
import os

from ...utils.logger import get_logger
from ...utils.i18n import _
from ..widgets.dashboard import DashboardView
from ..widgets.preview_panel import PreviewPanel
from ..widgets.operations_list import OperationsListView
from ..handlers import OperationsHandler


class JellyfixMainWindow(Adw.ApplicationWindow):
    """Main application window"""
    
    def __init__(self, application):
        """
        Initialize main window.
        
        Args:
            application: JellyfixApplication instance
        """
        super().__init__(application=application)

        self.logger = get_logger()

        # Window properties
        self.set_title(_("Jellyfix"))
        self.set_default_size(1200, 800)

        # Initialize operations handler
        self.operations_handler = OperationsHandler(self)

        # Clear recent libraries on start if configured
        self._check_clear_recent_on_start()

        # Build UI
        self._build_ui()

    def _check_clear_recent_on_start(self):
        """Clear recent libraries on startup if configured"""
        from ...utils.config_manager import ConfigManager
        config_manager = ConfigManager()
        if config_manager.get_clear_recent_on_start():
            config_manager.clear_recent_libraries()
            self.logger.debug("Cleared recent libraries on startup")
    
    def _build_ui(self):
        """Build user interface"""
        # Toast overlay for notifications
        self.toast_overlay = Adw.ToastOverlay()

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header = Adw.HeaderBar()
        
        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._create_menu())
        header.pack_end(menu_button)
        
        # Add header to main box
        main_box.append(header)
        
        # Create split view (list + preview)
        self.split_view = Adw.NavigationSplitView()
        self.split_view.set_show_content(True)
        self.split_view.set_min_sidebar_width(400)
        self.split_view.set_max_sidebar_width(600)
        self.split_view.set_sidebar_width_fraction(0.4)
        self.split_view.set_collapsed(False)
        self.split_view.set_vexpand(True)
        self.split_view.set_hexpand(True)

        # Left sidebar container
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_vexpand(True)

        # ViewStack switcher
        stack_switcher = Adw.ViewSwitcher()
        stack_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        # ViewStack for Dashboard/Operations
        self.sidebar_stack = Adw.ViewStack()
        self.sidebar_stack.set_vexpand(True)
        self.sidebar_stack.set_hexpand(True)

        # Connect switcher to stack
        stack_switcher.set_stack(self.sidebar_stack)

        # Dashboard view
        self.dashboard = DashboardView(
            on_scan_clicked=self.on_scan_library,
            on_process_clicked=self.on_process_files
        )
        dashboard_page = self.sidebar_stack.add_titled(
            self.dashboard,
            "dashboard",
            _("Dashboard")
        )
        dashboard_page.set_icon_name("view-grid-symbolic")

        # Operations list view
        self.operations_list = OperationsListView(
            on_operation_selected=self.on_operation_selected,
            on_apply_clicked=self.on_apply_operations
        )
        operations_page = self.sidebar_stack.add_titled(
            self.operations_list,
            "operations",
            _("Operations")
        )
        operations_page.set_icon_name("document-edit-symbolic")

        # Start with dashboard
        self.sidebar_stack.set_visible_child_name("dashboard")

        # Add switcher and stack to sidebar
        sidebar_box.append(stack_switcher)
        sidebar_box.append(self.sidebar_stack)

        sidebar_page = Adw.NavigationPage(
            title=_("Library"),
            child=sidebar_box
        )
        self.split_view.set_sidebar(sidebar_page)
        
        # Right panel: Preview
        self.preview_panel = PreviewPanel()
        self.preview_panel.set_vexpand(True)
        self.preview_panel.set_hexpand(True)
        
        # Connect callback for when user manually changes metadata via SearchDialog
        self.preview_panel.set_metadata_callback(self._on_metadata_changed)

        content_page = Adw.NavigationPage(
            title=_("Preview"),
            child=self.preview_panel
        )
        self.split_view.set_content(content_page)
        
        # Add split view to main box
        main_box.append(self.split_view)

        # Add main box to toast overlay
        self.toast_overlay.set_child(main_box)

        # Set content
        self.set_content(self.toast_overlay)
    
    def _create_menu(self):
        """
        Create application menu.

        Returns:
            Gio.Menu instance
        """
        from gi.repository import Gio

        menu = Gio.Menu()

        # Settings section
        settings_section = Gio.Menu()
        settings_section.append(_("Preferences"), "app.preferences")
        settings_section.append(_("Configure API Keys"), "app.configure_api")
        menu.append_section(None, settings_section)

        # Help section
        help_section = Gio.Menu()
        help_section.append(_("Help"), "app.help")
        help_section.append(_("About Jellyfix"), "app.about")
        menu.append_section(None, help_section)

        # Quit
        menu.append(_("Quit"), "app.quit")

        return menu

    def on_scan_library(self, widget=None):
        """
        Handle scan library request.

        Args:
            widget: Widget that triggered the action (may contain selected_directory)
        """
        self.logger.info("Scan library requested")

        # Check if directory was pre-selected (from dashboard drag-drop or recent)
        if widget and hasattr(widget, 'selected_directory'):
            directory = widget.selected_directory
            self.logger.info(f"Using pre-selected directory: {directory}")
            self._start_scan(directory)
            return

        # Open directory chooser
        def on_directory_selected(directory):
            """Callback when directory is selected"""
            self._start_scan(directory)

        self.operations_handler.select_directory(callback=on_directory_selected)

    def _start_scan(self, directory):
        """
        Start scanning a directory.

        Args:
            directory: Path to directory to scan
        """
        from pathlib import Path
        from ...utils.config_manager import ConfigManager

        # Ensure directory is a Path object
        if not isinstance(directory, Path):
            directory = Path(directory)

        self.logger.info(f"Directory selected: {directory}")

        # Update operations handler current directory
        self.operations_handler.current_directory = directory

        # Add to recent libraries
        config_manager = ConfigManager()
        config_manager.add_recent_library(str(directory))

        # Refresh dashboard recent libraries
        if hasattr(self.dashboard, 'refresh_recent_libraries'):
            self.dashboard.refresh_recent_libraries()

        # Show scanning toast
        toast = Adw.Toast(title=_("Scanning directory..."))
        toast.set_timeout(0)  # Indefinite
        self.toast_overlay.add_toast(toast)
        self.current_scan_toast = toast

        # Scan directory
        self.operations_handler.scan_directory(
            directory=directory,
            complete_callback=self.on_scan_complete
        )

    def load_paths(self, paths):
        """
        Load paths passed from command line (via file manager extension).
        
        Args:
            paths: List of file/folder paths to process
        """
        from pathlib import Path
        
        if not paths:
            self.logger.warning("load_paths called with empty paths")
            return
        
        self.logger.info(f"Loading {len(paths)} path(s) from command line")
        for p in paths:
            self.logger.debug(f"  Path: {p}")
        
        # Convert all paths to Path objects
        path_objects = [Path(p) for p in paths]
        
        # Check if we have folders selected
        folders = [p for p in path_objects if p.is_dir()]
        files = [p for p in path_objects if p.is_file()]
        
        self.logger.debug(f"Found {len(folders)} folders and {len(files)} files")
        
        if folders:
            # If folders are selected, use the first folder as the directory to scan
            # This is the most common case when right-clicking on a folder
            self.logger.debug(f"Folders: {[str(f) for f in folders]}")
            if len(folders) == 1:
                directory = folders[0]  # Scan THIS folder, not its parent
                self.logger.info(f"Single folder selected, scanning: {directory}")
            else:
                # Multiple folders - find common parent
                try:
                    directory = Path(os.path.commonpath([str(f) for f in folders]))
                except ValueError:
                    directory = folders[0]
                self.logger.info(f"Multiple folders, using common parent: {directory}")
        else:
            # Only files selected - use their common parent
            parent_dirs = set(p.parent for p in files)
            if len(parent_dirs) == 1:
                directory = parent_dirs.pop()
            else:
                try:
                    directory = Path(os.path.commonpath([str(d) for d in parent_dirs]))
                except ValueError:
                    directory = files[0].parent
            self.logger.info(f"Files selected, using parent: {directory}")
        
        self.logger.info(f"Will scan directory: {directory}")
        
        # Start scan after a short delay to ensure UI is ready
        from gi.repository import GLib
        GLib.timeout_add(100, lambda: self._start_scan(directory) or False)

    def on_scan_complete(self, files):
        """
        Handle scan completion.

        Args:
            files: ScanResult from scan
        """
        # Dismiss scanning toast
        if hasattr(self, 'current_scan_toast'):
            self.current_scan_toast.dismiss()

        # Get file counts from ScanResult
        total_files = files.total_files if hasattr(files, 'total_files') else len(files)

        self.logger.success(f"Scan found {total_files} files")

        # Show generating operations toast
        toast = Adw.Toast(title=_("Generating operations..."))
        toast.set_timeout(0)  # Indefinite
        self.toast_overlay.add_toast(toast)
        self.current_gen_toast = toast

        # Generate operations
        self.operations_handler.generate_operations(
            files=files,
            complete_callback=self.on_operations_generated
        )

    def on_operations_generated(self, operations):
        """
        Handle operations generation completion.

        Args:
            operations: List of generated operations
        """
        # Dismiss generating toast
        if hasattr(self, 'current_gen_toast'):
            self.current_gen_toast.dismiss()

        self.logger.success(f"{len(operations)} operations generated")

        # Show success toast
        toast = Adw.Toast(title=_("{} operations ready").format(len(operations)))
        toast.set_timeout(3)  # 3 seconds
        self.toast_overlay.add_toast(toast)

        # Display operations in list view
        self.operations_list.set_operations(operations)

        # Switch to operations view
        self.sidebar_stack.set_visible_child_name("operations")

    def on_apply_operations(self, operations):
        """
        Handle apply operations button click.

        Args:
            operations: List of operations to apply
        """
        self.logger.info(f"Applying {len(operations)} operations")

        # Store operations in handler
        self.operations_handler.operations = operations

        # Show confirmation dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Apply Operations?"),
            body=_("This will rename {} files. Continue?").format(len(operations))
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("apply", _("Apply"))
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "apply":
                self.logger.info("Executing operations")
                # Show progress toast
                toast = Adw.Toast(title=_("Applying operations..."))
                toast.set_timeout(0)
                self.toast_overlay.add_toast(toast)
                self.current_apply_toast = toast

                self.operations_handler.execute_operations(
                    complete_callback=self.on_execution_complete
                )

        dialog.connect("response", on_response)
        dialog.present()

    def on_process_files(self, widget=None):
        """
        Handle process files button click.

        Args:
            widget: Widget that triggered the action
        """
        self.logger.info("Process files requested")

        # Check if we have operations
        if not self.operations_handler.operations:
            self.logger.warning("No operations to process. Scan library first.")
            return

        # Show confirmation dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Execute Operations?"),
            body=_("This will rename {} files. Continue?").format(
                len(self.operations_handler.operations)
            )
        )
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("execute", _("Execute"))
        dialog.set_response_appearance("execute", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dialog, response):
            if response == "execute":
                self.logger.info("Executing operations")
                self.operations_handler.execute_operations(
                    complete_callback=self.on_execution_complete
                )

        dialog.connect("response", on_response)
        dialog.present()

    def on_execution_complete(self, results, dry_run=False):
        """
        Handle execution completion.

        Args:
            results: Execution results
            dry_run: Whether this was a dry run
        """
        if dry_run:
            self.logger.info(f"Dry-run complete: {len(results)} operations previewed")
            toast_msg = _("Dry-run: {} operations previewed").format(len(results))
        else:
            self.logger.success(f"Execution complete: {len(results)} operations")
            toast_msg = _("{} operations completed").format(len(results))

        # Show success toast
        toast = Adw.Toast(title=toast_msg)
        toast.set_timeout(5)  # 5 seconds
        self.toast_overlay.add_toast(toast)

        # Show completion dialog
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Complete!"),
            body=toast_msg
        )
        dialog.add_response("ok", _("OK"))
        dialog.present()

    def on_operation_selected(self, operation, index: int):
        """
        Handle operation selection.

        Args:
            operation: Selected RenameOperation
            index: Operation index
        """
        self.logger.debug(f"Operation selected: {operation.source.name}")

        # Show operation in preview panel
        self.preview_panel.show_operation(operation)

        # Try to fetch and show poster if it's a movie
        self._try_fetch_poster(operation)

    def _try_fetch_poster(self, operation):
        """
        Try to fetch and display poster for operation.

        Args:
            operation: RenameOperation instance
        """
        from ...core.detector import detect_media_type, MediaType
        from ...utils.helpers import extract_year, clean_filename
        import re

        # Check if metadata fetcher is available
        if not self.operations_handler.metadata_fetcher:
            self.logger.debug("No metadata fetcher available")
            return

        # Detect media type
        media_info = detect_media_type(operation.source)
        self.logger.debug(f"Media type: {media_info.media_type}")

        # Only fetch for movies and TV shows
        if media_info.media_type not in (MediaType.MOVIE, MediaType.TVSHOW):
            self.logger.debug("Not a movie or episode, skipping poster fetch")
            return

        # Get clean title and year
        title = clean_filename(operation.source.stem)
        year = extract_year(operation.source.stem)
        self.logger.debug(f"Fetching poster for: {title} ({year})")

        # Try to extract TMDB ID from destination path
        tmdb_id = None
        tmdb_match = re.search(r'\[tmdbid-(\d+)\]', str(operation.destination))
        if tmdb_match:
            tmdb_id = int(tmdb_match.group(1))
            self.logger.debug(f"Found TMDB ID: {tmdb_id}")

        def fetch_task():
            """Background poster fetch"""
            try:
                metadata = None

                # Try by ID first
                if tmdb_id:
                    self.logger.info(f"Fetching movie by TMDB ID: {tmdb_id}")
                    try:
                        metadata = self.operations_handler.metadata_fetcher.get_movie_by_id(tmdb_id)
                    except Exception as e:
                        self.logger.debug(f"get_movie_by_id failed: {e}")
                        # Fallback to search
                        metadata = self.operations_handler.metadata_fetcher.search_movie(title, year)
                else:
                    self.logger.info(f"Searching movie: {title} ({year})")
                    metadata = self.operations_handler.metadata_fetcher.search_movie(title, year)

                if metadata:
                    self.logger.debug(f"Got metadata: {metadata}")
                    if self.operations_handler.image_manager:
                        self.logger.debug("Downloading poster...")
                        poster_path = self.operations_handler.image_manager.download_poster(
                            metadata, size='medium'
                        )
                        if poster_path:
                            self.logger.info(f"Poster downloaded: {poster_path}")
                            GLib.idle_add(self.preview_panel.load_poster, poster_path)
                        else:
                            self.logger.warning("Poster download returned None")
                    else:
                        self.logger.warning("No image manager available")
                else:
                    self.logger.warning("No metadata found for movie")

            except Exception as e:
                self.logger.error(f"Could not fetch poster: {e}")
                import traceback
                traceback.print_exc()

        # Run in background thread
        import threading
        thread = threading.Thread(target=fetch_task, daemon=True)
        thread.start()

    def _fetch_metadata_and_poster(self, operation, media_info, title, year):
        """
        Fetch metadata and poster for operation.

        Args:
            operation: RenameOperation instance
            media_info: MediaInfo instance
            title: Extracted title
            year: Extracted year
        """
        from ...core.detector import MediaType

        def fetch_task():
            """Background metadata fetch"""
            try:
                metadata = None

                # Search for movie or TV show
                if media_info.media_type == MediaType.MOVIE:
                    metadata = self.operations_handler.metadata_fetcher.search_movie(
                        title, year
                    )
                elif media_info.media_type == MediaType.EPISODE:
                    # For episodes, extract show title
                    show_title = title  # TODO: Better extraction
                    metadata = self.operations_handler.metadata_fetcher.search_tvshow(
                        show_title, year
                    )

                if metadata:
                    # Update preview on main thread
                    GLib.idle_add(self._update_preview_with_metadata, metadata)

            except Exception as e:
                self.logger.error(f"Metadata fetch failed: {e}")

        # Run in background if metadata fetcher is available
        if self.operations_handler.metadata_fetcher:
            import threading
            thread = threading.Thread(target=fetch_task, daemon=True)
            thread.start()

    def _update_preview_with_metadata(self, metadata):
        """
        Update preview panel with fetched metadata.

        Args:
            metadata: Metadata instance
        """
        # Update preview with full metadata
        self.preview_panel.set_metadata(
            title=metadata.title,
            year=metadata.year,
            original_title=metadata.original_title,
            overview=metadata.overview,
            quality=None  # Keep existing quality
        )

        # Download poster
        if metadata.poster_path:
            self.operations_handler.download_poster(
                metadata,
                callback=self._on_poster_downloaded
            )

        return False  # Remove from GLib idle queue

    def _on_poster_downloaded(self, poster_path):
        """
        Handle poster download completion.

        Args:
            poster_path: Path to downloaded poster (or None)
        """
        if poster_path:
            self.preview_panel.load_poster(poster_path)

        return False  # Remove from GLib idle queue

    def _on_metadata_changed(self, operation, metadata):
        """
        Handle metadata change from SearchDialog.
        Updates the operation with new title/year and refreshes the UI.

        Args:
            operation: RenameOperation to update
            metadata: New Metadata selected by user
        """
        from ...utils.helpers import clean_filename, extract_quality_tag
        from ...utils.config import get_config
        import re

        config = get_config()
        self.logger.info(f"Updating operation with new metadata: {metadata.title} ({metadata.year})")

        # Find the operation in the list
        operations = self.operations_handler.operations
        op_index = None
        for i, op in enumerate(operations):
            if op.source == operation.source:
                op_index = i
                break

        if op_index is None:
            self.logger.warning("Operation not found in list")
            return

        # Build new destination path
        title = clean_filename(metadata.title)
        year = metadata.year

        # Get quality tag from original
        quality_tag = extract_quality_tag(operation.source.stem)
        if not quality_tag and config.add_quality_tag:
            from ...utils.helpers import detect_video_resolution
            quality_tag = detect_video_resolution(operation.source)

        # Build folder suffix with TMDB ID
        folder_suffix = ""
        if metadata.tmdb_id:
            folder_suffix = f" [tmdbid-{metadata.tmdb_id}]"

        # Build new name
        if year:
            base_name = f"{title} ({year})"
        else:
            base_name = f"{title}"

        if quality_tag:
            new_name = f"{base_name} - {quality_tag}{operation.source.suffix}"
        else:
            new_name = f"{base_name}{operation.source.suffix}"

        # Build new folder path
        expected_folder = f"{base_name}{folder_suffix}"

        # Determine new path
        base_dir = self.operations_handler.current_directory
        if operation.source.parent == base_dir:
            # File is loose in root
            new_folder = base_dir / expected_folder
        else:
            # File is in subfolder
            new_folder = base_dir / expected_folder

        new_path = new_folder / new_name

        # Update the operation
        from ...core.renamer import RenameOperation
        new_operation = RenameOperation(
            source=operation.source,
            destination=new_path,
            operation_type='move_rename' if new_path.parent != operation.source.parent else 'rename',
            reason=f"Manual update: {metadata.title} ({metadata.year})"
        )

        # Replace in list
        operations[op_index] = new_operation

        # Refresh the UI
        self.operations_list.set_operations(operations)

        # Update preview with new operation
        self.preview_panel.show_operation(new_operation)

        # Fetch new poster
        self._try_fetch_poster(new_operation)

        # Show success toast
        toast = Adw.Toast(title=f"Updated: {metadata.title} ({metadata.year})")
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)
