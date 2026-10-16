#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Jellyfix - Nautilus Extension
Adds a context menu option to organize video and subtitle files
for Jellyfin using the Jellyfix application.
"""

import gettext
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote

# Import 'gi' and explicitly require GTK and Nautilus versions.
# This is mandatory in modern PyGObject to prevent warnings and ensure API compatibility.
import gi
gi.require_version('Gtk', '4.0')

from gi.repository import GObject, Nautilus

# Folder scan limits. get_file_items() runs synchronously while Nautilus builds
# the context menu, so the media count inside selected folders must stay cheap:
# past either limit the scan stops and the menu falls back to a generic label.
FOLDER_SCAN_MAX_ENTRIES = 5000
FOLDER_SCAN_MAX_SECONDS = 0.15

VIDEO_EXTENSIONS = {
    '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
    '.m4v', '.mpg', '.mpeg', '.3gp', '.ogv'
}
SUBTITLE_EXTENSIONS = {'.srt', '.vtt', '.ass', '.sub', '.ssa'}

# --- Internationalization (i18n) Setup ---
APP_NAME = "jellyfix"

try:
    gettext.bindtextdomain(APP_NAME, "/usr/share/locale")
except Exception as e:
    print(f"Jellyfix Extension: Could not set up localization: {e}")


def _(message):
    """Domain-specific translation to avoid conflict with Nautilus' own textdomain."""
    return gettext.dgettext(APP_NAME, message)


class JellyfixExtension(GObject.GObject, Nautilus.MenuProvider):
    """
    Provides the context menu items for Nautilus to allow media organization.
    """

    def __init__(self):
        """Initializes the extension."""
        super().__init__()
        self.app_executable = 'jellyfix-gui'

        self.supported_subtitle_mimetypes = {
            'application/x-subrip', 'text/vtt', 'application/x-ass',
            'text/x-ssa', 'text/plain'  # text/plain for .sub files
        }


    def get_file_items(self, *args):
        """
        Returns menu items for the selected files or folders.
        The menu is shown if one or more supported video/subtitle files are selected,
        OR if one or more folders are selected (folders may contain media files).

        Note: Using *args for compatibility across Nautilus versions.
        The last argument is always the list of selected files.

        IMPORTANT: Nautilus calls this synchronously while building the context
        menu, so anything slow here freezes the file manager. Folder contents are
        only counted by a bounded scan (see _count_media_in_folders).
        """
        files = args[-1]

        # Separate folders from files
        folders = [f for f in files if f.is_directory()]
        regular_files = [f for f in files if not f.is_directory()]

        video_files = [f for f in regular_files if self._is_video_file(f)]
        subtitle_files = [f for f in regular_files if self._is_subtitle_file(f)]

        if not folders and not video_files and not subtitle_files:
            return []

        folder_counts = self._count_media_in_folders(folders) if folders else (0, 0)

        if folder_counts is not None and (
                len(video_files) + folder_counts[0] or len(subtitle_files) + folder_counts[1]):
            label = self._build_label(len(video_files) + folder_counts[0],
                                      len(subtitle_files) + folder_counts[1])
        elif folders and not video_files and not subtitle_files:
            if len(folders) == 1:
                label = _('Organize Folder with Jellyfix')
            else:
                label = _('Organize {0} Folders with Jellyfix').format(len(folders))
        else:
            label = _('Organize Media with Jellyfix')

        name = 'Jellyfix::Organize'

        # Pass all selected items (files and folders)
        all_items = folders + video_files + subtitle_files
        menu_item = Nautilus.MenuItem(name=name, label=label)
        menu_item.connect('activate', self._launch_application, all_items)
        return [menu_item]

    def _count_media_in_folders(self, folders: list) -> tuple[int, int] | None:
        """
        Counts videos and subtitles inside the folders, recursively.

        Returns (video_count, subtitle_count), or None when the count would be
        incomplete: a folder is not local, or the scan hit the entry/time limit.
        Uses os.scandir, which reads the file type from the directory listing
        without a stat() per file, skips hidden folders and does not follow
        symlinks.
        """
        deadline = time.monotonic() + FOLDER_SCAN_MAX_SECONDS
        scanned = 0
        videos = subtitles = 0

        pending = []
        for folder in folders:
            path = self._get_file_path(folder)
            if not path:
                return None
            pending.append(path)

        while pending:
            try:
                with os.scandir(pending.pop()) as entries:
                    for entry in entries:
                        scanned += 1
                        if scanned > FOLDER_SCAN_MAX_ENTRIES or time.monotonic() > deadline:
                            return None
                        if entry.is_dir(follow_symlinks=False):
                            if not entry.name.startswith('.'):
                                pending.append(entry.path)
                            continue
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in VIDEO_EXTENSIONS:
                            videos += 1
                        elif ext in SUBTITLE_EXTENSIONS:
                            subtitles += 1
            except OSError:
                continue

        return videos, subtitles

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
        Checks if a file is a supported video by its mimetype or extension.

        Any video/* mimetype is accepted instead of a fixed list: shared-mime-info
        2.5 renamed video/x-matroska to video/matroska and video/x-msvideo to
        video/vnd.avi, which silently hid the menu for .mkv and .avi files.
        """
        if not file_info or file_info.is_directory():
            return False

        if (file_info.get_mime_type() or '').startswith('video/'):
            return True
        return self._has_extension(file_info, VIDEO_EXTENSIONS)

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
                return self._has_extension(file_info, SUBTITLE_EXTENSIONS)
            return True

        # Fallback: check by extension
        return self._has_extension(file_info, SUBTITLE_EXTENSIONS)

    def _has_extension(self, file_info: Nautilus.FileInfo, extensions: set) -> bool:
        """
        Checks if the file name ends with one of the given extensions.
        """
        uri = file_info.get_uri()
        if not uri:
            return False
        path = Path(unquote(uri.replace('file://', '')))
        return path.suffix.lower() in extensions

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

            log_path = "/tmp/jellyfix-gui-debug.log"
            with open(log_path, "w") as log_file:
                subprocess.Popen(cmd, stdout=log_file, stderr=log_file, start_new_session=True)
                
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
            ], check=False, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Fallback if 'notify-send' is not installed.
            print(f"ERROR: [{title}] {message}")
