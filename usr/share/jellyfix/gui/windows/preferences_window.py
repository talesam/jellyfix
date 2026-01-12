#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/windows/preferences_window.py - Preferences window
#

"""
Preferences/Settings window for Jellyfix.

Settings available:
  - Subtitle handling (rename variants, add language codes, remove foreign)
  - Quality tag preferences
  - Metadata fetching
  - Kept subtitle languages
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw

from ...utils.logger import get_logger
from ...utils.i18n import _
from ...utils.config import get_config


class PreferencesWindow(Adw.PreferencesWindow):
    """Preferences window"""

    def __init__(self, parent):
        """
        Initialize preferences window.

        Args:
            parent: Parent window
        """
        super().__init__(transient_for=parent, modal=True)

        self.logger = get_logger()
        self.config = get_config()

        # Window properties
        self.set_title(_("Preferences"))
        self.set_default_size(650, 730)

        # Build UI
        self._build_ui()

    def _build_ui(self):
        """Build preferences UI"""
        # Subtitle preferences page
        subtitle_page = Adw.PreferencesPage(
            title=_("Subtitles"),
            icon_name="media-view-subtitles-symbolic"
        )

        # Subtitle handling group
        subtitle_group = Adw.PreferencesGroup(
            title=_("Subtitle Handling"),
            description=_("Configure how subtitles are processed")
        )

        # Rename language variants
        self.rename_variants_row = Adw.SwitchRow(
            title=_("Rename Language Variants"),
            subtitle=_("Rename .por2.srt, .eng2.srt to .por.srt, .eng.srt")
        )
        self.rename_variants_row.set_active(self.config.rename_por2)
        self.rename_variants_row.connect("notify::active", self._on_rename_variants_changed)
        subtitle_group.add(self.rename_variants_row)

        # Remove duplicate variants
        self.remove_duplicates_row = Adw.SwitchRow(
            title=_("Remove Duplicate Variants"),
            subtitle=_("Remove .lang2, .lang3 files after renaming")
        )
        self.remove_duplicates_row.set_active(self.config.remove_language_variants)
        self.remove_duplicates_row.connect("notify::active", self._on_remove_duplicates_changed)
        subtitle_group.add(self.remove_duplicates_row)

        # Add language codes
        self.add_lang_codes_row = Adw.SwitchRow(
            title=_("Add Language Codes"),
            subtitle=_("Add language codes to subtitles without them")
        )
        self.add_lang_codes_row.set_active(self.config.rename_no_lang)
        self.add_lang_codes_row.connect("notify::active", self._on_add_lang_changed)
        subtitle_group.add(self.add_lang_codes_row)

        # Remove foreign subtitles
        self.remove_foreign_row = Adw.SwitchRow(
            title=_("Remove Foreign Subtitles"),
            subtitle=_("Remove subtitles not in kept languages list")
        )
        self.remove_foreign_row.set_active(self.config.remove_foreign_subs)
        self.remove_foreign_row.connect("notify::active", self._on_remove_foreign_changed)
        subtitle_group.add(self.remove_foreign_row)

        # Min Portuguese words
        self.min_words_row = Adw.SpinRow.new_with_range(1, 20, 1)
        self.min_words_row.set_title(_("Minimum Portuguese Words"))
        self.min_words_row.set_subtitle(_("Min words to detect Portuguese subtitles"))
        self.min_words_row.set_value(self.config.min_pt_words)
        self.min_words_row.connect("notify::value", self._on_min_words_changed)
        subtitle_group.add(self.min_words_row)

        subtitle_page.add(subtitle_group)

        # Kept languages group
        languages_group = Adw.PreferencesGroup(
            title=_("Kept Languages"),
            description=_("Subtitles in these languages will be kept")
        )

        # Add all languages from config dynamically
        self.language_rows = {}
        for lang_code, lang_name in sorted(self.config.all_languages.items(), key=lambda x: x[1]):
            row = Adw.SwitchRow(
                title=_(lang_name),  # Translate language name
                subtitle=lang_code
            )
            row.set_active(lang_code in self.config.kept_languages)
            row.connect("notify::active", self._on_language_changed, lang_code)
            self.language_rows[lang_code] = row
            languages_group.add(row)

        subtitle_page.add(languages_group)

        self.add(subtitle_page)

        # Video preferences page
        video_page = Adw.PreferencesPage(
            title=_("Video"),
            icon_name="video-x-generic-symbolic"
        )

        # Video handling group
        video_group = Adw.PreferencesGroup(
            title=_("Video Handling"),
            description=_("Configure how videos are processed")
        )

        # Organize in folders
        self.organize_folders_row = Adw.SwitchRow(
            title=_("Organize in Folders"),
            subtitle=_("Organize TV episodes in Season folders")
        )
        self.organize_folders_row.set_active(self.config.organize_folders)
        self.organize_folders_row.connect("notify::active", self._on_organize_folders_changed)
        video_group.add(self.organize_folders_row)

        # Add quality tags
        self.quality_tag_row = Adw.SwitchRow(
            title=_("Add Quality Tags"),
            subtitle=_("Add resolution tags (1080p, 720p, etc) to filenames")
        )
        self.quality_tag_row.set_active(self.config.add_quality_tag)
        self.quality_tag_row.connect("notify::active", self._on_quality_tag_changed)
        video_group.add(self.quality_tag_row)

        # Use ffprobe
        self.ffprobe_row = Adw.SwitchRow(
            title=_("Use ffprobe for Detection"),
            subtitle=_("More accurate but slower quality detection")
        )
        self.ffprobe_row.set_active(self.config.use_ffprobe)
        self.ffprobe_row.connect("notify::active", self._on_ffprobe_changed)
        video_group.add(self.ffprobe_row)

        video_page.add(video_group)

        self.add(video_page)

        # Metadata preferences page
        metadata_page = Adw.PreferencesPage(
            title=_("Metadata"),
            icon_name="network-server-symbolic"
        )

        # Metadata group
        metadata_group = Adw.PreferencesGroup(
            title=_("Metadata Fetching"),
            description=_("Configure metadata from TMDB")
        )

        # Fetch metadata
        self.fetch_metadata_row = Adw.SwitchRow(
            title=_("Fetch Metadata"),
            subtitle=_("Download metadata and posters from TMDB")
        )
        self.fetch_metadata_row.set_active(self.config.fetch_metadata)
        self.fetch_metadata_row.connect("notify::active", self._on_fetch_metadata_changed)
        metadata_group.add(self.fetch_metadata_row)

        metadata_page.add(metadata_group)

        self.add(metadata_page)

        # General preferences page
        general_page = Adw.PreferencesPage(
            title=_("General"),
            icon_name="preferences-system-symbolic"
        )

        # Application group
        app_group = Adw.PreferencesGroup(
            title=_("Application"),
            description=_("General application settings")
        )

        # Keep recent libraries
        from ...utils.config_manager import ConfigManager
        self.config_manager = ConfigManager()

        self.keep_recent_row = Adw.SwitchRow(
            title=_("Keep Recent Libraries"),
            subtitle=_("Remember recently scanned libraries between sessions")
        )
        self.keep_recent_row.set_active(self.config_manager.get_keep_recent_libraries())
        self.keep_recent_row.connect("notify::active", self._on_keep_recent_changed)
        app_group.add(self.keep_recent_row)

        general_page.add(app_group)

        # File cleanup group
        cleanup_group = Adw.PreferencesGroup(
            title=_("File Cleanup"),
            description=_("Configure which files to remove")
        )

        # Remove non-media files
        self.remove_non_media_row = Adw.SwitchRow(
            title=_("Remove Non-Media Files"),
            subtitle=_("Remove all files that are not .srt or .mp4")
        )
        self.remove_non_media_row.set_active(self.config.remove_non_media)
        self.remove_non_media_row.connect("notify::active", self._on_remove_non_media_changed)
        cleanup_group.add(self.remove_non_media_row)

        general_page.add(cleanup_group)

        self.add(general_page)

    def _on_rename_variants_changed(self, switch, param):
        """Handle rename variants toggle"""
        self.config.rename_por2 = switch.get_active()
        self.logger.debug(f"Rename variants: {self.config.rename_por2}")

    def _on_remove_duplicates_changed(self, switch, param):
        """Handle remove duplicate variants toggle"""
        self.config.remove_language_variants = switch.get_active()
        self.logger.debug(f"Remove duplicate variants: {self.config.remove_language_variants}")

    def _on_add_lang_changed(self, switch, param):
        """Handle add language codes toggle"""
        self.config.rename_no_lang = switch.get_active()
        self.logger.debug(f"Add language codes: {switch.get_active()}")

    def _on_remove_foreign_changed(self, switch, param):
        """Handle remove foreign subtitles toggle"""
        self.config.remove_foreign_subs = switch.get_active()
        self.logger.debug(f"Remove foreign subtitles: {self.config.remove_foreign_subs}")

    def _on_min_words_changed(self, spin, param):
        """Handle min Portuguese words change"""
        self.config.min_pt_words = int(spin.get_value())
        self.logger.debug(f"Min Portuguese words: {self.config.min_pt_words}")

    def _on_language_changed(self, switch, param, lang_code: str):
        """
        Handle kept language toggle.

        Args:
            switch: Switch widget
            param: Parameter
            lang_code: Language code (por, eng, etc)
        """
        if switch.get_active():
            if lang_code not in self.config.kept_languages:
                self.config.kept_languages.append(lang_code)
        else:
            if lang_code in self.config.kept_languages:
                self.config.kept_languages.remove(lang_code)

        self.logger.debug(f"Kept languages: {self.config.kept_languages}")

    def _on_organize_folders_changed(self, switch, param):
        """Handle organize folders toggle"""
        self.config.organize_folders = switch.get_active()
        self.logger.debug(f"Organize folders: {self.config.organize_folders}")

    def _on_quality_tag_changed(self, switch, param):
        """Handle quality tag toggle"""
        self.config.add_quality_tag = switch.get_active()
        self.logger.debug(f"Add quality tag: {self.config.add_quality_tag}")

    def _on_ffprobe_changed(self, switch, param):
        """Handle ffprobe toggle"""
        self.config.use_ffprobe = switch.get_active()
        self.logger.debug(f"Use ffprobe: {self.config.use_ffprobe}")

    def _on_fetch_metadata_changed(self, switch, param):
        """Handle fetch metadata toggle"""
        self.config.fetch_metadata = switch.get_active()
        self.logger.debug(f"Fetch metadata: {self.config.fetch_metadata}")

    def _on_keep_recent_changed(self, switch, param):
        """Handle keep recent libraries toggle"""
        self.config_manager.set_keep_recent_libraries(switch.get_active())
        self.logger.debug(f"Keep recent libraries: {switch.get_active()}")

    def _on_remove_non_media_changed(self, switch, param):
        """Handle remove non-media files toggle"""
        self.config.remove_non_media = switch.get_active()
        self.config_manager.set('remove_non_media', self.config.remove_non_media)
        self.logger.debug(f"Remove non-media files: {self.config.remove_non_media}")

