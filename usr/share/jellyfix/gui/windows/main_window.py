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

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import os
from pathlib import Path

from gi.repository import Adw, GLib, Gtk, Pango

from ...core.subtitle_manager import SubtitleManager
from ...utils.i18n import _
from ...utils.logger import get_logger
from ..handlers import OperationsHandler
from ..widgets.dashboard import DashboardView
from ..widgets.operations_list import OperationsListView
from ..widgets.preview_panel import PreviewPanel


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
        # Main split view: operations sidebar (left) | preview content (right)
        self.split_view = Adw.OverlaySplitView()
        self.split_view.set_min_sidebar_width(360)
        self.split_view.set_max_sidebar_width(520)
        self.split_view.set_sidebar_width_fraction(0.40)
        self.split_view.set_sidebar(self._build_sidebar())
        self.split_view.set_content(self._build_content())

        # Toast overlay as outermost wrapper
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(self.split_view)
        self.set_content(self.toast_overlay)

    def _build_sidebar(self):
        """Build the work area sidebar: Dashboard + Operations list (left)."""
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)

        app_icon = Gtk.Image.new_from_icon_name("jellyfix")
        app_icon.set_pixel_size(20)
        header.pack_start(app_icon)

        title_label = Gtk.Label(label=_("Jellyfix"))
        title_label.add_css_class("heading")
        header.set_title_widget(title_label)

        toolbar.add_top_bar(header)

        # Stack: welcome/dashboard page and operations list page
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_vexpand(True)
        self.content_stack.set_hexpand(True)

        self.dashboard = DashboardView(
            on_scan_clicked=self.on_scan_library,
            on_process_clicked=self.on_process_files,
        )
        self.content_stack.add_named(self.dashboard, "welcome")

        self.operations_list = OperationsListView(
            on_operation_selected=self.on_operation_selected,
            on_apply_clicked=self.on_apply_operations,
            on_download_subs_clicked=self.on_download_batch_subtitles,
        )
        self.content_stack.add_named(self.operations_list, "operations")

        toolbar.set_content(self.content_stack)

        return toolbar

    def _build_content(self):
        """Build the preview content pane (right)."""
        toolbar = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.set_show_start_title_buttons(False)
        # Hide the automatic window title on the right pane
        header.set_title_widget(Gtk.Box())

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._create_menu())
        header.pack_end(menu_button)

        toolbar.add_top_bar(header)

        # Preview panel fills the content area
        self.preview_panel = PreviewPanel()
        self.preview_panel.set_vexpand(True)
        self.preview_panel.set_hexpand(True)
        self.preview_panel.set_metadata_callback(self._on_metadata_changed)
        self.preview_panel.set_download_subs_callback(self.on_download_subtitles)

        toolbar.set_content(self.preview_panel)

        return toolbar
    
    # ── Menu ────────────────────────────────────────────────────────────────

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
            self.logger.info("Filtering scan results...")
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
        self.content_stack.set_visible_child_name("operations")

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
            nfo_files=[f for f in scan_result.nfo_files if is_selected(f)],
            non_media_files=[f for f in scan_result.non_media_files if is_selected(f)]
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
        import re

        from ...core.detector import MediaType, detect_media_type
        from ...utils.helpers import clean_filename, extract_year

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
        progress_window.set_title("")
        progress_window.set_titlebar(Gtk.Box())  # Hide title bar
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

        # Spinner for activity indication
        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.start()
        box.append(spinner)

        # Progress bar (only visible for multiple files)
        progress_bar = Gtk.ProgressBar()
        progress_bar.set_fraction(0.0)
        progress_bar.set_show_text(True)
        if len(operations) > 1:
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
            "window": progress_window,
            "status": status_label,
            "bar": progress_bar,
            "spinner": spinner,
            "file": file_label,
            "total": len(operations),
            "current": 0,
            "success": 0,
            "downloaded": 0,
            "pulse_id": None,
        }

        def batch_task():
            """Background batch download task"""
            try:
                import re

                from ...utils.config import get_config
                
                config = get_config()
                requested_langs = set(config.kept_languages) if config.kept_languages else {'por', 'eng'}
                
                for i, op in enumerate(operations):
                    # Update status to show current file being processed
                    GLib.idle_add(self._update_batch_status, i, op.source.name)
                    
                    # Extract TMDB info from destination path
                    dest_str = str(op.destination)
                    
                    # Extract TMDB ID
                    tmdb_match = re.search(r'\[tmdbid-(\d+)\]', dest_str)
                    tmdb_id = int(tmdb_match.group(1)) if tmdb_match else None
                    
                    # Extract title and year from destination
                    # Pattern: "Title (Year)" or episode "Title S01E01"
                    dest_name = op.destination.stem
                    
                    # Remove quality tags
                    dest_name = re.sub(r'\s*-\s*(2160p|1080p|720p|480p|4K).*', '', dest_name)
                    
                    # Check if it's an episode (S01E01 pattern)
                    episode_match = re.search(r'(.+?)\s+S(\d+)E(\d+)', dest_name)
                    year_match = re.search(r'\((\d{4})\)', dest_name)
                    
                    tmdb_title = None
                    tmdb_year = None
                    is_episode = False
                    season = None
                    episode_num = None
                    
                    if episode_match:
                        # TV Episode
                        tmdb_title = episode_match.group(1).strip()
                        season = int(episode_match.group(2))
                        episode_num = int(episode_match.group(3))
                        is_episode = True
                        # Try to get year from folder
                        folder_year = re.search(r'\((\d{4})\)', str(op.destination.parent))
                        if folder_year:
                            tmdb_year = int(folder_year.group(1))
                    elif year_match:
                        # Movie
                        tmdb_year = int(year_match.group(1))
                        tmdb_title = dest_name[:year_match.start()].strip()
                    else:
                        tmdb_title = dest_name.strip()
                    
                    # IMPORTANT: Use original title from TMDB for subtitle search
                    # Subtitle providers index by original (usually English) title
                    original_title = None
                    if tmdb_id:
                        try:
                            from ...core.metadata import MetadataFetcher
                            fetcher = MetadataFetcher()
                            if is_episode:
                                metadata = fetcher.get_tvshow_by_id(tmdb_id)
                            else:
                                metadata = fetcher.get_movie_by_id(tmdb_id)
                            
                            if metadata and metadata.original_title:
                                original_title = metadata.original_title
                                self.logger.info(f"Using original title for subtitle search: '{original_title}' (translated: '{tmdb_title}')")
                        except Exception as e:
                            self.logger.debug(f"Could not fetch original title: {e}")
                    
                    # Use original title if available, fallback to translated title
                    search_title = original_title or tmdb_title
                    
                    # Log what we're using for subtitle search
                    self.logger.info(f"TMDB info for subtitle search: title='{search_title}', year={tmdb_year}, episode={is_episode}")

                    # Collect existing subtitle files before download
                    existing_subs = set(
                        f.name
                        for f in op.source.parent.iterdir()
                        if f.is_file()
                        and f.suffix.lower() in (".srt", ".ass", ".ssa", ".sub", ".vtt")
                    )

                    # Download with TMDB metadata
                    try:
                        results = self.subtitle_manager.download_subtitles(
                            op.source,
                            tmdb_title=search_title,
                            tmdb_year=tmdb_year,
                            tmdb_id=tmdb_id,
                            is_episode=is_episode,
                            season=season,
                            episode=episode_num,
                        )
                        if results:
                            found_langs = set(results.keys())

                            # Count only truly new subtitle files
                            new_subs = (
                                set(
                                    f.name
                                    for f in op.source.parent.iterdir()
                                    if f.is_file()
                                    and f.suffix.lower()
                                    in (".srt", ".ass", ".ssa", ".sub", ".vtt")
                                )
                                - existing_subs
                            )
                            self.batch_progress["downloaded"] += len(new_subs)
                            
                            # Check if we got all requested languages
                            missing = requested_langs - found_langs
                            if missing:
                                # Partial success - save for manual search
                                if 'partial_ops' not in self.batch_progress:
                                    self.batch_progress['partial_ops'] = []
                                self.batch_progress['partial_ops'].append({
                                    'op': op,
                                    'missing': missing,
                                    'found': found_langs
                                })
                                self.batch_progress['partial'] = self.batch_progress.get('partial', 0) + 1
                            else:
                                # Full success
                                self.batch_progress['success'] += 1
                        else:
                            # No subtitles found at all
                            if 'failed_ops' not in self.batch_progress:
                                self.batch_progress['failed_ops'] = []
                            self.batch_progress['failed_ops'].append(op)
                    except Exception as e:
                        self.logger.error(f"Error downloading for {op.source.name}: {e}")

                    # Update progress bar after each file is processed
                    GLib.idle_add(self._update_batch_progress, i + 1)
                
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

    def _update_batch_status(self, index, filename):
        """Update status text and current file label (before download)"""
        if not hasattr(self, 'batch_progress'):
            return
        total = self.batch_progress["total"]
        self.batch_progress["status"].set_text(
            _("Searching subtitles ({}/{})").format(index + 1, total)
        )
        self.batch_progress["file"].set_text(filename)

    def _update_batch_progress(self, completed):
        """Update progress bar after a file has been processed"""
        if not hasattr(self, "batch_progress"):
            return
        total = self.batch_progress['total']
        fraction = completed / total
        self.batch_progress["bar"].set_fraction(fraction)
        self.batch_progress["bar"].set_text(f"{int(fraction * 100)}%")

    def _on_batch_complete(self):
        """Handle batch completion"""
        if hasattr(self, 'batch_progress'):
            # Stop spinner
            self.batch_progress["spinner"].stop()

            # Stop pulsing if active
            if self.batch_progress.get('pulse_id'):
                GLib.source_remove(self.batch_progress['pulse_id'])
                
            self.batch_progress['window'].close()
            
            total = self.batch_progress['total']
            success = self.batch_progress['success']
            downloaded = self.batch_progress['downloaded']
            partial = self.batch_progress.get('partial', 0)
            partial_ops = self.batch_progress.get('partial_ops', [])
            failed_ops = self.batch_progress.get('failed_ops', [])
            
            # Store for manual search
            self._last_partial_ops = partial_ops
            self._last_failed_ops = failed_ops
            
            del self.batch_progress
            
            # Determine message and options based on results
            sub_word = _("subtitle") if downloaded == 1 else _("subtitles")
            vid_word = _("video") if success == 1 else _("videos")
            
            if downloaded == 0:
                heading = _("No Subtitles Found")
                body = _("Could not find any subtitles automatically.\nTry manual search?")
                show_manual = True
            elif partial > 0 or failed_ops:
                # Some languages missing
                heading = _("Partial Success")
                
                # Build detailed message
                if partial_ops:
                    missing_langs = set()
                    for item in partial_ops:
                        missing_langs.update(item['missing'])
                    missing_str = ", ".join(sorted(missing_langs))
                    body = _("Downloaded {} {}.\n\nMissing languages: {}\nTry manual search?").format(
                        downloaded, sub_word, missing_str
                    )
                else:
                    total_word = _("video") if total == 1 else _("videos")
                    body = _("Downloaded {} {} for {} of {} {}.\nTry manual search for missing?").format(
                        downloaded, sub_word, success, total, total_word
                    )
                show_manual = True
            else:
                heading = _("Download Complete")
                body = _("Downloaded {} {} for {} {} (all languages).").format(
                    downloaded, sub_word, success, vid_word
                )
                show_manual = False
            
            # Show summary dialog
            dialog = Adw.MessageDialog(
                transient_for=self,
                heading=heading,
                body=body
            )
            
            if show_manual:
                dialog.add_response("manual", _("Manual Search"))
                dialog.set_response_appearance("manual", Adw.ResponseAppearance.SUGGESTED)
            
            dialog.add_response("rescan", _("Rescan Now"))
            dialog.add_response("ok", _("OK"))
            
            if not show_manual:
                dialog.set_response_appearance("rescan", Adw.ResponseAppearance.SUGGESTED)
            
            def on_response(dialog, response):
                if response == "rescan":
                    if hasattr(self.operations_handler, 'current_directory'):
                        self._start_scan(self.operations_handler.current_directory)
                elif response == "manual":
                    # Open manual search for first item with missing languages
                    if self._last_partial_ops:
                        self._open_manual_subtitle_search(self._last_partial_ops[0]['op'])
                    elif self._last_failed_ops:
                        self._open_manual_subtitle_search(self._last_failed_ops[0])
                    else:
                        self._open_manual_subtitle_search()
            
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

    def _open_manual_subtitle_search(self, operation=None):
        """
        Open manual subtitle search dialog.
        
        Args:
            operation: Optional RenameOperation to search for. If None, uses current selection.
        """
        import re

        from .subtitle_search_dialog import SubtitleSearchDialog
        
        # Get operation from current selection if not provided
        if operation is None:
            operation = self.preview_panel.current_operation
        
        if operation is None:
            self.logger.warning("No operation selected for manual subtitle search")
            return
        
        # Extract info from destination
        dest_name = operation.destination.stem
        
        # Remove quality tags
        dest_name = re.sub(r'\s*-\s*(2160p|1080p|720p|480p|4K).*', '', dest_name)
        
        # Check if it's an episode
        episode_match = re.search(r'(.+?)\s+S(\d+)E(\d+)', dest_name)
        year_match = re.search(r'\((\d{4})\)', dest_name)
        
        if episode_match:
            query = episode_match.group(1).strip()
            season = int(episode_match.group(2))
            episode_num = int(episode_match.group(3))
            is_episode = True
            # Try to get year from folder
            folder_year = re.search(r'\((\d{4})\)', str(operation.destination.parent))
            year = int(folder_year.group(1)) if folder_year else None
        elif year_match:
            year = int(year_match.group(1))
            query = dest_name[:year_match.start()].strip()
            is_episode = False
            season = None
            episode_num = None
        else:
            query = dest_name.strip()
            year = None
            is_episode = False
            season = None
            episode_num = None
        
        # Open dialog
        dialog = SubtitleSearchDialog(
            parent=self,
            video_path=operation.source,
            initial_query=query,
            is_episode=is_episode,
            season=season,
            episode=episode_num,
            year=year,
            on_download=lambda path: self._on_manual_subtitle_downloaded(path)
        )
        dialog.present()
    
    def _on_manual_subtitle_downloaded(self, path):
        """Handle subtitle downloaded from manual search"""
        if path:
            self.logger.success(f"Subtitle downloaded: {path.name}")
            toast = Adw.Toast(title=_("Subtitle downloaded: {}").format(path.name))
            toast.set_timeout(3)
            self.toast_overlay.add_toast(toast)


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
        import re

        from ...core.renamer import Renamer
        from ...utils.helpers import is_subtitle_file, normalize_spaces

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
