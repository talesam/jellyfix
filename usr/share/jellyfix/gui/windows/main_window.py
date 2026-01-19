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

from gi.repository import Gtk, Adw, GLib, Pango
from pathlib import Path
import os

from ...utils.logger import get_logger
from ...utils.i18n import _
from ..widgets.dashboard import DashboardView
from ..widgets.preview_panel import PreviewPanel
from ..widgets.operations_list import OperationsListView
from ..handlers import OperationsHandler
from ...core.subtitle_manager import SubtitleManager


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
        self.subtitle_manager = SubtitleManager()

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
            on_apply_clicked=self.on_apply_operations,
            on_download_subs_clicked=self.on_download_batch_subtitles
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
        
        # Connect callback for subtitle download
        self.preview_panel.set_download_subs_callback(self.on_download_subtitles)

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
            
            # Check for selected paths (specific files/folders from drag-drop)
            if hasattr(widget, 'selected_paths') and widget.selected_paths:
                files = [p for p in widget.selected_paths if p.is_file()]
                folders = [p for p in widget.selected_paths if p.is_dir()]
                
                if files:
                    self.selected_files = files
                    self.logger.info(f"Selected specific files: {[f.name for f in files]}")
                
                if folders:
                    self.selected_folders = folders
                    self.logger.info(f"Selected specific folders: {[f.name for f in folders]}")
            
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

        # Store selected items for filtering later
        self.selected_folders = []
        self.selected_files = []

        if folders:
            # If folders are selected, use the first folder as the directory to scan
            # This is the most common case when right-clicking on a folder
            self.logger.debug(f"Folders: {[str(f) for f in folders]}")
            if len(folders) == 1:
                directory = folders[0]  # Scan THIS folder, not its parent
                self.logger.info(f"Single folder selected, scanning: {directory}")
                # No filtering needed for single folder
            else:
                # Multiple folders - scan parent but filter to selected folders only
                try:
                    directory = Path(os.path.commonpath([str(f) for f in folders]))
                except ValueError:
                    directory = folders[0].parent
                self.logger.info(f"Multiple folders selected, scanning parent: {directory}")
                self.logger.info(f"Will filter to only these folders: {[str(f) for f in folders]}")
                # Store selected folders for filtering
                self.selected_folders = folders
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
            self.logger.info(f"Will filter to only these files: {[f.name for f in files]}")
            # Store selected files for filtering
            self.selected_files = files

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

        # Apply folder/file filtering if selected
        has_folders = hasattr(self, 'selected_folders') and self.selected_folders
        has_files = hasattr(self, 'selected_files') and self.selected_files
        
        if has_folders or has_files:
            self.logger.info(f"Filtering scan results...")
            files = self._filter_scan_result(files)
            
            # Clear filters
            if hasattr(self, 'selected_folders'):
                self.selected_folders = []
            if hasattr(self, 'selected_files'):
                self.selected_files = []
        else:
            self.logger.debug("No filtering - processing all files from scan")

        # Get file counts from ScanResult
        total_files = files.total_files if hasattr(files, 'total_files') else len(files)

        self.logger.success(f"Scan found {total_files} files")

        # Show generating operations toast
        toast = Adw.Toast(title=_("Generating operations..."))
        toast.set_timeout(0)  # Indefinite
        self.toast_overlay.add_toast(toast)
        self.current_gen_toast = toast

        # Generate operations with filtered scan result
        self.operations_handler.generate_operations(
            scan_result=files,
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

    def _filter_scan_result(self, scan_result):
        """
        Filter ScanResult to include only selected files/folders.
        Uses self.selected_folders and self.selected_files.

        Args:
            scan_result: Original ScanResult from scanner

        Returns:
            Filtered ScanResult
        """
        from ...core.scanner import ScanResult
        from pathlib import Path
        
        selected_folders = getattr(self, 'selected_folders', []) or []
        selected_files = getattr(self, 'selected_files', []) or []
        
        # Convert selected files to resolved paths for robust comparison
        # Also create a set of selected file stems (names without extension) 
        # to catch related files (like subtitles) if we decide to
        resolved_files = set()
        selected_stems = set()
        
        for f in selected_files:
            try:
                path = Path(f).resolve()
                resolved_files.add(path)
                selected_stems.add(path.stem)
            except Exception:
                pass

        def is_selected(file_path):
            """Check if file matches selection filters"""
            try:
                file_path = Path(file_path)
                file_resolved = file_path.resolve()
                
                # Check file filter first
                if selected_files:
                    if file_resolved in resolved_files:
                        return True
                        
                    # Also include subtitles that match the selected video file stem?
                    # This is usually desired behavior when drag-dropping a movie file
                    # If we drag "movie.mkv", we probably want "movie.srt" too.
                    # But let's be strict for now as per request: "dragged 1 file, wants 1 file processed"
                    # However, operations might break if we rename video but not subtitle.
                    # Let's keep strict match for now to fix the "scanning everything" issue.
                    pass
                
                # Check folder filter
                if selected_folders:
                    for folder in selected_folders:
                        try:
                            folder_resolved = folder.resolve()
                            if file_resolved == folder_resolved or folder_resolved in file_resolved.parents:
                                return True
                        except Exception:
                            if str(file_path).startswith(str(folder)):
                                return True
                    
                # If we have file filters but no match, return False
                if selected_files:
                    return False
                    
                # If we have folder filters but no match, return False
                if selected_folders:
                    return False
                    
                # No filters active
                return True
                
            except Exception as e:
                self.logger.warning(f"Error checking file {file_path}: {e}")
                return False

        # Filter all file lists
        filtered_result = ScanResult(
            video_files=[f for f in scan_result.video_files if is_selected(f)],
            subtitle_files=[f for f in scan_result.subtitle_files if is_selected(f)],
            image_files=[f for f in scan_result.image_files if is_selected(f)],
            other_files=[f for f in scan_result.other_files if is_selected(f)],
            variant_subtitles=[f for f in scan_result.variant_subtitles if is_selected(f)],
            no_lang_subtitles=[f for f in scan_result.no_lang_subtitles if is_selected(f)],
            foreign_subtitles=[f for f in scan_result.foreign_subtitles if is_selected(f)],
            kept_subtitles=[f for f in scan_result.kept_subtitles if is_selected(f)],
            unwanted_images=[f for f in scan_result.unwanted_images if is_selected(f)],
            nfo_files=[f for f in scan_result.nfo_files if is_selected(f)]
        )

        # Update statistics
        filtered_result.total_movies = len(filtered_result.video_files) # Approximate
        filtered_result.total_episodes = 0 # We don't distinguish in filtered view without re-scanning

        # Log filtering results
        original_count = len(scan_result.video_files) + len(scan_result.subtitle_files)
        filtered_count = len(filtered_result.video_files) + len(filtered_result.subtitle_files)
        self.logger.info(f"Filtered: {original_count} → {filtered_count} files")

        return filtered_result

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
                is_movie = media_info.media_type == MediaType.MOVIE

                # Try by ID first
                if tmdb_id:
                    if is_movie:
                        self.logger.info(f"Fetching movie by TMDB ID: {tmdb_id}")
                        try:
                            metadata = self.operations_handler.metadata_fetcher.get_movie_by_id(tmdb_id)
                        except Exception as e:
                            self.logger.debug(f"get_movie_by_id failed: {e}")
                            # Fallback to search
                            metadata = self.operations_handler.metadata_fetcher.search_movie(title, year)
                    else:
                        self.logger.info(f"Fetching TV show by TMDB ID: {tmdb_id}")
                        try:
                            metadata = self.operations_handler.metadata_fetcher.get_tvshow_by_id(tmdb_id)
                        except Exception as e:
                            self.logger.debug(f"get_tvshow_by_id failed: {e}")
                            # Fallback to search
                            metadata = self.operations_handler.metadata_fetcher.search_tvshow(title, year)
                else:
                    if is_movie:
                        self.logger.info(f"Searching movie: {title} ({year})")
                        metadata = self.operations_handler.metadata_fetcher.search_movie(title, year)
                    else:
                        self.logger.info(f"Searching TV show: {title}")
                        metadata = self.operations_handler.metadata_fetcher.search_tvshow(title, year)

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

    def on_download_batch_subtitles(self, operations):
        """
        Handle batch subtitle download request.
        
        Args:
            operations: List of RenameOperation instances (videos)
        """
        if not operations:
            return

        self.logger.info(f"Batch subtitle download requested for {len(operations)} videos")
        
        if not self.subtitle_manager.is_available():
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("Feature Unavailable"),
                body=_("The 'subliminal' library is not installed.\nPlease install it to use this feature.")
            )
            dialog.add_response("ok", _("OK"))
            dialog.present()
            return

        # Show progress dialog
        # Since Adw doesn't have a built-in progress dialog, we can use a custom Gtk.Window 
        # or use the Toast overlay with a spinner, but for batch operations a modal dialog is better.
        # Let's creating a simple modal window.
        
        progress_window = Gtk.Window(transient_for=self, modal=True)
        progress_window.set_title(_("Downloading Subtitles"))
        progress_window.set_default_size(400, 200)
        progress_window.set_resizable(False)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        
        # Status Label
        status_label = Gtk.Label(label=_("Preparing..."))
        status_label.set_wrap(True)
        status_label.set_justify(Gtk.Justification.CENTER)
        box.append(status_label)
        
        # Progress Bar
        progress_bar = Gtk.ProgressBar()
        progress_bar.set_fraction(0.0)
        progress_bar.set_show_text(True)
        box.append(progress_bar)
        
        # Current file label
        file_label = Gtk.Label(label="")
        file_label.set_wrap(True)
        file_label.add_css_class("dim-label")
        file_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        box.append(file_label)
        
        progress_window.set_child(box)
        progress_window.present()
        
        # Store for updating
        self.batch_progress = {
            'window': progress_window,
            'status': status_label,
            'bar': progress_bar,
            'file': file_label,
            'total': len(operations),
            'current': 0,
            'success': 0,
            'downloaded': 0,
            'pulse_id': None
        }
        
        # If single file, start pulsing for indeterminate progress
        if len(operations) == 1:
            self.batch_progress['pulse_id'] = GLib.timeout_add(100, self._pulse_progress)
        
        def batch_task():
            """Background batch download task"""
            try:
                for i, op in enumerate(operations):
                    # Update progress UI
                    GLib.idle_add(self._update_batch_progress, i, op.source.name)
                    
                    # Download
                    try:
                        results = self.subtitle_manager.download_subtitles(op.source)
                        if results:
                            count = sum(len(paths) for paths in results.values())
                            self.batch_progress['downloaded'] += count
                            if count > 0:
                                self.batch_progress['success'] += 1
                    except Exception as e:
                        self.logger.error(f"Error downloading for {op.source.name}: {e}")
                
                # Finish
                GLib.idle_add(self._on_batch_complete)
                
            except Exception as e:
                self.logger.error(f"Batch download failed: {e}")
                GLib.idle_add(self._on_batch_error, str(e))
                
        # Run in background thread
        import threading
        thread = threading.Thread(target=batch_task, daemon=True)
        thread.start()

    def _pulse_progress(self):
        """Pulse progress bar for indeterminate status"""
        if hasattr(self, 'batch_progress'):
            self.batch_progress['bar'].pulse()
            return True
        return False

    def _update_batch_progress(self, index, filename):
        """Update batch progress dialog"""
        if not hasattr(self, 'batch_progress'):
            return
            
        total = self.batch_progress['total']
        
        # Only update fraction for multiple files to avoid overriding pulse
        if total > 1:
            fraction = index / total
            self.batch_progress['bar'].set_fraction(fraction)
            self.batch_progress['bar'].set_text(f"{int(fraction * 100)}%")
        
        self.batch_progress['status'].set_text(_("Searching subtitles ({}/{})").format(index + 1, total))
        self.batch_progress['file'].set_text(filename)

    def _on_batch_complete(self):
        """Handle batch completion"""
        if hasattr(self, 'batch_progress'):
            # Stop pulsing if active
            if self.batch_progress.get('pulse_id'):
                GLib.source_remove(self.batch_progress['pulse_id'])
                
            self.batch_progress['window'].close()
            
            total = self.batch_progress['total']
            success = self.batch_progress['success']
            downloaded = self.batch_progress['downloaded']
            
            del self.batch_progress
            
            # Show summary dialog
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=_("Download Complete"),
                body=_("Processed {} videos.\nDownloaded {} subtitles for {} videos.").format(
                    total, downloaded, success
                )
            )
            dialog.add_response("rescan", _("Rescan Now"))
            dialog.add_response("ok", _("OK"))
            dialog.set_response_appearance("rescan", Adw.ResponseAppearance.SUGGESTED)
            
            def on_response(dialog, response):
                if response == "rescan":
                    if hasattr(self.operations_handler, 'current_directory'):
                        self._start_scan(self.operations_handler.current_directory)
            
            dialog.connect("response", on_response)
            dialog.present()

    def _on_batch_error(self, error_msg):
        """Handle batch error"""
        if hasattr(self, 'batch_progress'):
            # Stop pulsing if active
            if self.batch_progress.get('pulse_id'):
                GLib.source_remove(self.batch_progress['pulse_id'])
                
            self.batch_progress['window'].close()
            del self.batch_progress
            
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Batch Error"),
            body=_("An error occurred during batch download:\n{}").format(error_msg)
        )
        dialog.add_response("ok", _("OK"))
        dialog.present()

    def on_download_subtitles(self, operation):
        """
        Handle download subtitles request (single file).
        Redirects to batch handler for consistent UX.
        
        Args:
            operation: RenameOperation instance
        """
        self.on_download_batch_subtitles([operation])

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
        Re-plans all operations for the video using the new metadata, respecting all config settings.

        Args:
            operation: RenameOperation to update
            metadata: New Metadata selected by user
        """
        from ...utils.helpers import normalize_spaces, is_subtitle_file
        from ...core.renamer import Renamer
        import re

        self.logger.info(f"Re-planning operations with new metadata: {metadata.title} ({metadata.year})")

        # Get current operations list
        operations = self.operations_handler.operations

        # Find video operation and all related operations
        video_source = operation.source
        video_stem_original = video_source.stem
        video_normalized = normalize_spaces(video_stem_original)

        # Find indices of all operations related to this video
        related_indices = []
        video_index = None

        for i, op in enumerate(operations):
            if op.source == video_source:
                # This is the video itself
                video_index = i
                related_indices.append(i)
            else:
                # Check if this operation is related to the video
                file_stem = op.source.stem

                # For subtitles, remove language code before comparing
                if is_subtitle_file(op.source):
                    base_match = re.match(r'(.+?)\.([a-z]{2,3}\d?)(\.forced)?$', file_stem, re.IGNORECASE)
                    if base_match:
                        file_base = base_match.group(1)
                    else:
                        file_base = file_stem

                    if normalize_spaces(file_base) == video_normalized or file_base == video_stem_original:
                        related_indices.append(i)

                # For NFO and image files, compare full stem
                elif op.source.suffix.lower() in ['.nfo', '.jpg', '.png', '.jpeg']:
                    if normalize_spaces(file_stem) == video_normalized or file_stem == video_stem_original:
                        related_indices.append(i)

        if video_index is None:
            self.logger.warning("Video operation not found in list")
            return

        # Create a Renamer instance with the current metadata_fetcher (preserves cache)
        renamer = Renamer(metadata_fetcher=self.operations_handler.metadata_fetcher)

        # Re-plan operations for this video with the new metadata
        # This will respect ALL config settings (remove_foreign_subs, organize_folders, etc.)
        new_operations = renamer.replan_for_video_with_metadata(
            video_path=video_source,
            metadata=metadata,
            all_operations=operations
        )

        if not new_operations:
            self.logger.warning("Failed to re-plan operations")
            return

        # Remove old related operations (in reverse order to maintain indices)
        for i in sorted(related_indices, reverse=True):
            del operations[i]

        # Insert new operations at the position where the video was
        insert_position = min(related_indices)
        for i, new_op in enumerate(new_operations):
            operations.insert(insert_position + i, new_op)

        # Log what was updated
        self.logger.info(f"Replaced {len(related_indices)} old operations with {len(new_operations)} new operations")
        for new_op in new_operations:
            if new_op.operation_type == 'delete':
                self.logger.info(f"  - DELETE: {new_op.source.name} ({new_op.reason})")
            else:
                self.logger.info(f"  - {new_op.operation_type.upper()}: {new_op.source.name} → {new_op.destination.name}")

        # Update the operations handler
        self.operations_handler.operations = operations

        # Refresh the UI
        self.operations_list.set_operations(operations)

        # Update preview with the first new operation (the video)
        if new_operations:
            self.preview_panel.show_operation(new_operations[0])

            # Fetch new poster
            self._try_fetch_poster(new_operations[0])

        # Show success toast with count of operations
        toast = Adw.Toast(title=f"Updated: {metadata.title} ({metadata.year}) - {len(new_operations)} operations")
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)
