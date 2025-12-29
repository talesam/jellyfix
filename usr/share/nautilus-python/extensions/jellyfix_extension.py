#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Jellyfix - Nautilus Extension
Adds a context menu option to organize video and subtitle files
for Jellyfin using the Jellyfix application.
"""

import gettext
import subprocess
from pathlib import Path
from urllib.parse import unquote

# Import 'gi' and explicitly require GTK and Nautilus versions.
# This is mandatory in modern PyGObject to prevent warnings and ensure API compatibility.
import gi
gi.require_version('Gtk', '4.0')

from gi.repository import GObject, Nautilus

# --- Internationalization (i18n) Setup ---
APP_NAME = "jellyfix"

try:
    # Set the default domain for this script. gettext will automatically find
    # the message catalogs in the system's standard locale directories.
    gettext.textdomain(APP_NAME)
except Exception as e:
    print(f"Jellyfix Extension: Could not set up localization: {e}")

# Define the global translation function.
_ = gettext.gettext


class JellyfixExtension(GObject.GObject, Nautilus.MenuProvider):
    """
    Provides the context menu items for Nautilus to allow media organization.
    """

    def __init__(self):
        """Initializes the extension."""
        super().__init__()
        self.app_executable = 'jellyfix-gui'

        # Using a set provides O(1) lookup time, which is more efficient than a list.
        self.supported_video_mimetypes = {
            'video/mp4', 'video/x-matroska', 'video/webm', 'video/quicktime',
            'video/x-msvideo', 'video/x-ms-wmv', 'video/mpeg', 'video/x-m4v',
            'video/mp2t', 'video/x-flv', 'video/3gpp', 'video/ogg'
        }

        self.supported_subtitle_mimetypes = {
            'application/x-subrip', 'text/vtt', 'application/x-ass',
            'text/x-ssa', 'text/plain'  # text/plain for .sub files
        }

        # Subtitle extensions for fallback detection
        self.subtitle_extensions = {'.srt', '.vtt', '.ass', '.sub', '.ssa'}

    def get_file_items(self, *args):
        """
        Returns menu items for the selected files or folders.
        The menu is shown if one or more supported video/subtitle files are selected,
        OR if one or more folders are selected (folders may contain media files).

        Note: Using *args for compatibility across Nautilus versions.
        The last argument is always the list of selected files.
        """
        files = args[-1]

        # Separate folders from files
        folders = [f for f in files if f.is_directory()]
        regular_files = [f for f in files if not f.is_directory()]

        video_files = [f for f in regular_files if self._is_video_file(f)]
        subtitle_files = [f for f in regular_files if self._is_subtitle_file(f)]

        # Count media files in folders (for label display)
        folder_video_count = 0
        folder_subtitle_count = 0
        for folder in folders:
            folder_path = self._get_file_path(folder)
            if folder_path:
                v_count, s_count = self._count_media_in_folder(Path(folder_path))
                folder_video_count += v_count
                folder_subtitle_count += s_count

        # Show menu if we have any media files OR any folders selected
        total_videos = len(video_files) + folder_video_count
        total_subtitles = len(subtitle_files) + folder_subtitle_count
        
        if not folders and not video_files and not subtitle_files:
            return []

        # Build the label based on what's selected
        if folders and not video_files and not subtitle_files:
            # Only folders selected - show folder count or media count if available
            if total_videos > 0 or total_subtitles > 0:
                label = self._build_label(total_videos, total_subtitles)
            else:
                if len(folders) == 1:
                    label = _('Organize Folder with Jellyfix')
                else:
                    label = _('Organize {0} Folders with Jellyfix').format(len(folders))
        else:
            label = self._build_label(total_videos, total_subtitles)

        name = 'Jellyfix::Organize'

        # Pass all selected items (files and folders)
        all_items = folders + video_files + subtitle_files
        menu_item = Nautilus.MenuItem(name=name, label=label)
        menu_item.connect('activate', self._launch_application, all_items)
        return [menu_item]

    def _count_media_in_folder(self, folder_path: Path) -> tuple[int, int]:
        """
        Counts video and subtitle files in a folder (non-recursive, just first level).
        Returns (video_count, subtitle_count).
        """
        video_extensions = {'.mp4', '.mkv', '.webm', '.mov', '.avi', '.wmv', 
                           '.mpeg', '.mpg', '.m4v', '.ts', '.flv', '.3gp', '.ogv'}
        subtitle_extensions = {'.srt', '.vtt', '.ass', '.sub', '.ssa'}
        
        video_count = 0
        subtitle_count = 0
        
        try:
            for item in folder_path.iterdir():
                if item.is_file():
                    ext = item.suffix.lower()
                    if ext in video_extensions:
                        video_count += 1
                    elif ext in subtitle_extensions:
                        subtitle_count += 1
        except (PermissionError, OSError):
            pass
        
        return video_count, subtitle_count

    def _build_label(self, num_videos: int, num_subtitles: int) -> str:
        """
        Builds the menu label based on the number of videos and subtitles.
        """
        if num_videos > 0 and num_subtitles > 0:
            # Both videos and subtitles
            if num_videos == 1 and num_subtitles == 1:
                return _('Organize 1 Video and 1 Subtitle')
            elif num_videos == 1:
                return _('Organize 1 Video and {0} Subtitles').format(num_subtitles)
            elif num_subtitles == 1:
                return _('Organize {0} Videos and 1 Subtitle').format(num_videos)
            else:
                return _('Organize {0} Videos and {1} Subtitles').format(num_videos, num_subtitles)
        elif num_videos > 0:
            # Only videos
            if num_videos == 1:
                return _('Organize Video')
            else:
                return _('Organize {0} Videos').format(num_videos)
        else:
            # Only subtitles
            if num_subtitles == 1:
                return _('Organize Subtitle')
            else:
                return _('Organize {0} Subtitles').format(num_subtitles)

    def _is_video_file(self, file_info: Nautilus.FileInfo) -> bool:
        """
        Checks if a file is a supported video by its mimetype.
        """
        if not file_info or file_info.is_directory():
            return False

        return file_info.get_mime_type() in self.supported_video_mimetypes

    def _is_subtitle_file(self, file_info: Nautilus.FileInfo) -> bool:
        """
        Checks if a file is a supported subtitle by its mimetype or extension.
        """
        if not file_info or file_info.is_directory():
            return False

        # Check mimetype first
        if file_info.get_mime_type() in self.supported_subtitle_mimetypes:
            # For text/plain, verify by extension
            if file_info.get_mime_type() == 'text/plain':
                return self._has_subtitle_extension(file_info)
            return True

        # Fallback: check by extension
        return self._has_subtitle_extension(file_info)

    def _has_subtitle_extension(self, file_info: Nautilus.FileInfo) -> bool:
        """
        Checks if the file has a subtitle extension.
        """
        uri = file_info.get_uri()
        if not uri:
            return False
        path = Path(unquote(uri.replace('file://', '')))
        return path.suffix.lower() in self.subtitle_extensions

    def _get_file_path(self, file_info: Nautilus.FileInfo) -> str | None:
        """
        Gets the local file path from a Nautilus.FileInfo object by parsing its URI.
        """
        uri = file_info.get_uri()
        if not uri.startswith('file://'):
            return None
        # Decode URL-encoded characters (e.g., %20 -> space) and remove the prefix.
        return unquote(uri[7:])

    def _launch_application(self, menu_item: Nautilus.MenuItem, files: list[Nautilus.FileInfo]):
        """
        Launches the Jellyfix application with the selected files or folders.
        """
        file_paths = []
        for f in files:
            path = self._get_file_path(f)
            if path and Path(path).exists():
                file_paths.append(path)

        if not file_paths:
            self._show_error_notification(
                _("No valid local files selected"),
                _("Could not get the path for the selected files.")
            )
            return

        try:
            cmd = [self.app_executable] + file_paths
            print(f"Jellyfix Extension: Launching command: {cmd}")
            
            # Use Popen with proper error handling
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Don't wait for process, just log if there's immediate failure
            # Check if process started successfully
            import time
            time.sleep(0.5)
            if process.poll() is not None:
                # Process exited immediately - there was an error
                _, stderr = process.communicate()
                error_msg = stderr.decode('utf-8', errors='replace') if stderr else "Unknown error"
                print(f"Jellyfix Extension: Process failed: {error_msg}")
                self._show_error_notification(
                    _("Application Launch Error"),
                    error_msg[:200]
                )
                
        except FileNotFoundError:
            print(f"Jellyfix Extension: Executable not found: {self.app_executable}")
            self._show_error_notification(
                _("Application Not Found"),
                _("Could not find '{0}'. Is Jellyfix installed?").format(self.app_executable)
            )
        except Exception as e:
            print(f"Jellyfix Extension: Error launching '{self.app_executable}': {e}")
            self._show_error_notification(
                _("Application Launch Error"),
                _("Failed to start Jellyfix: {0}").format(str(e))
            )

    def _show_error_notification(self, title: str, message: str):
        """
        Displays a desktop error notification using 'notify-send'.
        """
        try:
            subprocess.run([
                'notify-send',
                '--icon=dialog-error',
                f'--app-name={APP_NAME}',
                title,
                message
            ], check=False)
        except FileNotFoundError:
            # Fallback if 'notify-send' is not installed.
            print(f"ERROR: [{title}] {message}")
