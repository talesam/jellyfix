#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/windows/subtitle_search_dialog.py - Manual subtitle search dialog
#

"""
Dialog for manually searching subtitles.
Shows a list of results with language and provider for the user to choose.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Pango
from pathlib import Path
from typing import Optional, Callable, List
import threading

from ...utils.i18n import _
from ...utils.logger import get_logger
from ...core.subtitle_manager import SubtitleManager, SubtitleResult


class SubtitleResultRow(Gtk.ListBoxRow):
    """A single subtitle search result row with enhanced UX"""
    
    def __init__(self, result: SubtitleResult):
        super().__init__()
        self.result = result
        
        # Main box
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        # Left side: Language info
        lang_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lang_box.set_valign(Gtk.Align.CENTER)
        lang_box.set_size_request(120, -1)
        
        # Language name (full name like "Português (Brasil)")
        lang_name = result.language_name or result.language.upper()
        lang_label = Gtk.Label(label=lang_name)
        lang_label.set_halign(Gtk.Align.START)
        lang_label.add_css_class("heading")
        lang_box.append(lang_label)
        
        # Badges row (forced, SDH, etc.)
        badges_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        badges_box.set_halign(Gtk.Align.START)
        
        if result.is_forced:
            forced_badge = Gtk.Label(label="FORCED")
            forced_badge.add_css_class("badge")
            forced_badge.add_css_class("warning")
            badges_box.append(forced_badge)
        
        if result.is_hearing_impaired:
            hi_badge = Gtk.Label(label="SDH")
            hi_badge.add_css_class("badge")
            hi_badge.add_css_class("accent")
            badges_box.append(hi_badge)
        
        if badges_box.get_first_child():
            lang_box.append(badges_box)
        
        box.append(lang_box)
        
        # Center: Release info
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        info_box.set_valign(Gtk.Align.CENTER)
        
        # Release name (cleaned up)
        release_text = result.release_name or _("Unknown release")
        # Remove common noise from release names
        for noise in ['srt', '.srt', 'SubRip', 'sub', 'subtitle']:
            release_text = release_text.replace(noise, '').strip()
        
        release_label = Gtk.Label(label=release_text)
        release_label.set_halign(Gtk.Align.START)
        release_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        release_label.set_max_width_chars(50)
        release_label.set_wrap(False)
        info_box.append(release_label)
        
        # Meta info row (provider + size)
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        meta_box.set_halign(Gtk.Align.START)
        
        # Provider
        provider_label = Gtk.Label(label=result.provider.capitalize())
        provider_label.add_css_class("dim-label")
        provider_label.add_css_class("caption")
        meta_box.append(provider_label)
        
        # File size (if available)
        if result.file_size > 0:
            size_str = self._format_size(result.file_size)
            size_label = Gtk.Label(label=f"• {size_str}")
            size_label.add_css_class("dim-label")
            size_label.add_css_class("caption")
            meta_box.append(size_label)
        
        # Download count (popularity indicator)
        if result.download_count > 0:
            pop_label = Gtk.Label(label=f"• ⬇ {self._format_count(result.download_count)}")
            pop_label.add_css_class("dim-label")
            pop_label.add_css_class("caption")
            meta_box.append(pop_label)
        
        info_box.append(meta_box)
        box.append(info_box)
        
        self.set_child(box)
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def _format_count(self, count: int) -> str:
        """Format download count in human readable format"""
        if count < 1000:
            return str(count)
        elif count < 1000000:
            return f"{count / 1000:.1f}K"
        else:
            return f"{count / 1000000:.1f}M"


class SubtitleSearchDialog(Adw.Window):
    """Dialog for manually searching subtitles"""

    def __init__(self, parent: Gtk.Window, video_path: Path,
                 initial_query: str = "",
                 is_episode: bool = False,
                 season: Optional[int] = None,
                 episode: Optional[int] = None,
                 year: Optional[int] = None,
                 on_download: Optional[Callable[[Path], None]] = None):
        super().__init__()
        
        self.parent = parent
        self.video_path = video_path
        self.is_episode = is_episode
        self.season = season
        self.episode = episode
        self.year = year
        self.on_download = on_download
        self.logger = get_logger()
        self.subtitle_manager = SubtitleManager()
        self.results: List[SubtitleResult] = []
        self.selected_result: Optional[SubtitleResult] = None
        
        # Window properties
        self.set_title(_("Search Subtitles"))
        self.set_default_size(600, 500)
        self.set_modal(True)
        self.set_transient_for(parent)
        
        # Build UI
        self._build_ui()
        
        # Set initial query
        if initial_query:
            self.search_entry.set_text(initial_query)
            # Auto-search if we have a query
            GLib.timeout_add(200, lambda: self._on_search(None) or False)
    
    def _build_ui(self):
        """Build dialog UI"""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        
        # Download button in header
        self.download_btn = Gtk.Button(label=_("Download"))
        self.download_btn.add_css_class("suggested-action")
        self.download_btn.set_sensitive(False)
        self.download_btn.connect("clicked", self._on_download_clicked)
        header.pack_end(self.download_btn)
        
        main_box.append(header)
        
        # Content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(16)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        
        # Search box
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text(_("Enter movie or show title..."))
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self._on_search)
        search_box.append(self.search_entry)
        
        # Episode info entries (for TV shows)
        self.season_entry = Gtk.SpinButton.new_with_range(1, 99, 1)
        self.season_entry.set_value(self.season or 1)
        self.season_entry.set_tooltip_text(_("Season"))
        search_box.append(self.season_entry)
        
        self.episode_entry = Gtk.SpinButton.new_with_range(1, 999, 1)
        self.episode_entry.set_value(self.episode or 1)
        self.episode_entry.set_tooltip_text(_("Episode"))
        search_box.append(self.episode_entry)
        
        # Hide episode entries for movies
        if not self.is_episode:
            self.season_entry.set_visible(False)
            self.episode_entry.set_visible(False)
        
        search_btn = Gtk.Button()
        search_btn.set_icon_name("system-search-symbolic")
        search_btn.add_css_class("suggested-action")
        search_btn.connect("clicked", self._on_search)
        search_box.append(search_btn)
        
        content_box.append(search_box)
        
        # Type toggle
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        type_box.set_halign(Gtk.Align.CENTER)
        
        self.movie_btn = Gtk.ToggleButton(label=_("Movie"))
        self.movie_btn.set_active(not self.is_episode)
        self.movie_btn.connect("toggled", self._on_type_toggle)
        type_box.append(self.movie_btn)
        
        self.episode_btn = Gtk.ToggleButton(label=_("Episode"))
        self.episode_btn.set_active(self.is_episode)
        self.episode_btn.set_group(self.movie_btn)
        self.episode_btn.connect("toggled", self._on_type_toggle)
        type_box.append(self.episode_btn)
        
        content_box.append(type_box)
        
        # Results list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.results_list = Gtk.ListBox()
        self.results_list.add_css_class("boxed-list")
        self.results_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.results_list.connect("row-selected", self._on_result_selected)
        
        # Placeholder
        self.placeholder = Adw.StatusPage(
            icon_name="system-search-symbolic",
            title=_("Search for Subtitles"),
            description=_("Enter a title and click search")
        )
        self.results_list.set_placeholder(self.placeholder)
        
        scrolled.set_child(self.results_list)
        content_box.append(scrolled)
        
        # Status label
        self.status_label = Gtk.Label()
        self.status_label.add_css_class("dim-label")
        content_box.append(self.status_label)
        
        main_box.append(content_box)
        self.set_content(main_box)
    
    def _on_type_toggle(self, button):
        """Handle type toggle"""
        is_episode = self.episode_btn.get_active()
        self.season_entry.set_visible(is_episode)
        self.episode_entry.set_visible(is_episode)
        self.is_episode = is_episode
    
    def _on_search(self, widget):
        """Handle search button click"""
        query = self.search_entry.get_text().strip()
        if not query:
            return
        
        # Clear previous results
        while True:
            row = self.results_list.get_first_child()
            if row is None:
                break
            self.results_list.remove(row)
        
        self.results = []
        self.selected_result = None
        self.download_btn.set_sensitive(False)
        
        # Update status
        self.status_label.set_text(_("Searching..."))
        
        # Get episode info
        season = int(self.season_entry.get_value()) if self.is_episode else None
        episode = int(self.episode_entry.get_value()) if self.is_episode else None
        
        # Search in background
        def do_search():
            try:
                results = self.subtitle_manager.search_subtitles_manual(
                    query=query,
                    is_episode=self.is_episode,
                    season=season,
                    episode=episode,
                    year=self.year
                )
                GLib.idle_add(self._show_results, results)
            except Exception as e:
                self.logger.error(f"Search failed: {e}")
                GLib.idle_add(self._show_error, str(e))
        
        thread = threading.Thread(target=do_search, daemon=True)
        thread.start()
    
    def _show_results(self, results: List[SubtitleResult]):
        """Show search results in list"""
        self.results = results
        
        if not results:
            self.status_label.set_text(_("No subtitles found"))
            self.placeholder.set_title(_("No Results"))
            self.placeholder.set_description(_("Try a different search term"))
            return
        
        self.status_label.set_text(_("Found {} subtitles").format(len(results)))
        
        for result in results:
            row = SubtitleResultRow(result)
            self.results_list.append(row)
    
    def _show_error(self, message: str):
        """Show error message"""
        self.status_label.set_text(_("Error: {}").format(message))
    
    def _on_result_selected(self, listbox, row):
        """Handle result selection"""
        if row:
            self.selected_result = row.result
            self.download_btn.set_sensitive(True)
        else:
            self.selected_result = None
            self.download_btn.set_sensitive(False)
    
    def _on_download_clicked(self, button):
        """Handle download button click"""
        if not self.selected_result:
            return
        
        self.status_label.set_text(_("Downloading..."))
        self.download_btn.set_sensitive(False)
        
        def do_download():
            try:
                path = self.subtitle_manager.download_selected_subtitle(
                    self.selected_result,
                    self.video_path
                )
                GLib.idle_add(self._on_download_complete, path)
            except Exception as e:
                self.logger.error(f"Download failed: {e}")
                GLib.idle_add(self._show_error, str(e))
        
        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()
    
    def _on_download_complete(self, path: Optional[Path]):
        """Handle download completion"""
        if path:
            self.status_label.set_text(_("Downloaded: {}").format(path.name))
            
            # Call callback
            if self.on_download:
                self.on_download(path)
            
            # Close dialog after short delay
            GLib.timeout_add(1000, self.close)
        else:
            self.status_label.set_text(_("Download failed"))
            self.download_btn.set_sensitive(True)
