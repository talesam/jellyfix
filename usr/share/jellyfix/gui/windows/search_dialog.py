#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/windows/search_dialog.py - Manual title search dialog
#

"""
Dialog for manually searching movie/TV show titles on TMDB.
Shows a grid of results with posters for the user to choose.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib
from typing import Optional, Callable
import threading
import urllib.request
import tempfile
import os

from ...utils.i18n import _
from ...utils.logger import get_logger
from ...core.metadata import MetadataFetcher, Metadata


class SearchResultItem(Gtk.FlowBoxChild):
    """A single search result item with poster and title"""
    
    def __init__(self, result: dict, is_movie: bool = True):
        super().__init__()
        self.result = result
        self.is_movie = is_movie
        self.metadata = None
        
        # Main box
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_spacing(8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        
        # Poster frame
        frame = Gtk.Frame()
        frame.add_css_class("card")
        
        self.poster_image = Gtk.Picture()
        self.poster_image.set_size_request(120, 180)
        self.poster_image.set_content_fit(Gtk.ContentFit.COVER)
        
        # Default placeholder
        self.poster_image.set_resource("/com/github/jellyfix/placeholder.png")
        
        frame.set_child(self.poster_image)
        box.append(frame)
        
        # Title
        title = result.get('title') or result.get('name', 'Unknown')
        title_label = Gtk.Label(label=title)
        title_label.set_max_width_chars(15)
        title_label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        title_label.set_wrap(True)
        title_label.set_lines(2)
        title_label.add_css_class("heading")
        box.append(title_label)
        
        # Year
        date = result.get('release_date') or result.get('first_air_date', '')
        if date:
            year = date[:4]
            year_label = Gtk.Label(label=year)
            year_label.add_css_class("dim-label")
            box.append(year_label)
        
        self.set_child(box)
        
        # Load poster async
        poster_path = result.get('poster_path')
        if poster_path:
            self._load_poster_async(f"https://image.tmdb.org/t/p/w185{poster_path}")
    
    def _load_poster_async(self, url: str):
        """Load poster image asynchronously"""
        def do_load():
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    data = response.read()
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as f:
                        f.write(data)
                        temp_path = f.name
                    
                    # Update UI from main thread
                    GLib.idle_add(self._set_poster, temp_path)
            except Exception as e:
                print(f"Error loading poster: {e}")
        
        thread = threading.Thread(target=do_load, daemon=True)
        thread.start()
    
    def _set_poster(self, path: str):
        """Set poster from path (called from main thread)"""
        try:
            self.poster_image.set_filename(path)
            # Clean up temp file after a delay
            GLib.timeout_add(5000, lambda: os.unlink(path) if os.path.exists(path) else None)
        except Exception:
            pass


class SearchDialog(Adw.Dialog):
    """Dialog for manually searching TMDB"""
    
    def __init__(self, parent: Gtk.Window, is_movie: bool = True,
                 on_select: Optional[Callable[[Metadata], None]] = None):
        super().__init__()
        
        self.parent_window = parent
        self.is_movie = is_movie
        self.on_select = on_select
        self.logger = get_logger()
        self.fetcher = MetadataFetcher()
        self.search_results = []
        self.selected_metadata = None
        
        # Dialog properties
        self.set_title(_("Search Title"))
        self.set_content_width(870)
        self.set_content_height(800)
        
        self._build_ui()
    
    def _build_ui(self):
        """Build dialog UI"""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_spacing(12)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        
        # Header bar with close button
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main_box.append(header)
        
        # Search entry
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        search_box.set_spacing(8)
        search_box.set_margin_start(16)
        search_box.set_margin_end(16)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_hexpand(True)
        self.search_entry.set_placeholder_text(_("Enter movie or series name..."))
        self.search_entry.connect("activate", self._on_search)
        search_box.append(self.search_entry)
        
        search_button = Gtk.Button(label=_("Search"))
        search_button.add_css_class("suggested-action")
        search_button.connect("clicked", self._on_search)
        search_box.append(search_button)
        
        main_box.append(search_box)
        
        # Type toggle (movie vs TV)
        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        type_box.set_halign(Gtk.Align.CENTER)
        type_box.set_spacing(8)
        type_box.set_margin_top(8)
        
        self.movie_toggle = Gtk.ToggleButton(label=_("Movie"))
        self.movie_toggle.set_active(self.is_movie)
        self.movie_toggle.connect("toggled", self._on_type_toggle)
        type_box.append(self.movie_toggle)
        
        self.tv_toggle = Gtk.ToggleButton(label=_("TV Series"))
        self.tv_toggle.set_active(not self.is_movie)
        self.tv_toggle.connect("toggled", self._on_type_toggle)
        type_box.append(self.tv_toggle)
        
        # Group toggles
        self.movie_toggle.set_group(self.tv_toggle)
        
        main_box.append(type_box)
        
        # Results area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_margin_start(16)
        scrolled.set_margin_end(16)
        scrolled.set_margin_top(8)
        scrolled.set_margin_bottom(8)
        
        # FlowBox for results grid
        self.results_flowbox = Gtk.FlowBox()
        self.results_flowbox.set_valign(Gtk.Align.START)
        self.results_flowbox.set_max_children_per_line(4)
        self.results_flowbox.set_min_children_per_line(2)
        self.results_flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.results_flowbox.set_homogeneous(True)
        self.results_flowbox.connect("child-activated", self._on_result_selected)
        
        scrolled.set_child(self.results_flowbox)
        main_box.append(scrolled)
        
        # Status label
        self.status_label = Gtk.Label()
        self.status_label.add_css_class("dim-label")
        self.status_label.set_margin_start(16)
        self.status_label.set_margin_end(16)
        main_box.append(self.status_label)
        
        # Spinner for loading
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)
        main_box.append(self.spinner)
        
        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_spacing(8)
        button_box.set_margin_start(16)
        button_box.set_margin_end(16)
        
        cancel_button = Gtk.Button(label=_("Cancel"))
        cancel_button.connect("clicked", lambda b: self.close())
        button_box.append(cancel_button)
        
        self.select_button = Gtk.Button(label=_("Apply"))
        self.select_button.add_css_class("suggested-action")
        self.select_button.set_sensitive(False)
        self.select_button.connect("clicked", self._on_select_clicked)
        button_box.append(self.select_button)
        
        main_box.append(button_box)
        
        self.set_child(main_box)
    
    def _on_type_toggle(self, button):
        """Handle type toggle"""
        self.is_movie = self.movie_toggle.get_active()
    
    def _on_search(self, widget):
        """Handle search button click"""
        query = self.search_entry.get_text().strip()
        if not query:
            return
        
        # Show loading
        self.spinner.set_visible(True)
        self.spinner.start()
        self.status_label.set_text(_("Searching..."))
        
        # Clear previous results
        while child := self.results_flowbox.get_first_child():
            self.results_flowbox.remove(child)
        
        # Search in background
        def do_search():
            try:
                tmdb = self.fetcher._init_tmdb()
                if not tmdb:
                    GLib.idle_add(self._show_error, _("TMDB not configured"))
                    return
                
                if self.is_movie:
                    results = tmdb['movie'].search(query)
                else:
                    results = tmdb['tv'].search(query)
                
                # Convert to list
                result_list = []
                for i, r in enumerate(results):
                    if i >= 20:  # Limit to 20 results
                        break
                    result_list.append({
                        'id': r.id,
                        'title': getattr(r, 'title', None) or getattr(r, 'name', 'Unknown'),
                        'name': getattr(r, 'name', None),
                        'release_date': getattr(r, 'release_date', None),
                        'first_air_date': getattr(r, 'first_air_date', None),
                        'poster_path': getattr(r, 'poster_path', None),
                        'overview': getattr(r, 'overview', None),
                    })
                
                GLib.idle_add(self._show_results, result_list)
                
            except Exception as e:
                self.logger.error(f"Search error: {e}")
                GLib.idle_add(self._show_error, str(e))
        
        thread = threading.Thread(target=do_search, daemon=True)
        thread.start()
    
    def _show_results(self, results: list):
        """Show search results in grid"""
        self.spinner.stop()
        self.spinner.set_visible(False)
        
        self.search_results = results
        
        if not results:
            self.status_label.set_text(_("No results found"))
            return
        
        self.status_label.set_text(f"{len(results)} {_('results')}")
        
        for result in results:
            item = SearchResultItem(result, self.is_movie)
            self.results_flowbox.append(item)
    
    def _show_error(self, message: str):
        """Show error message"""
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.status_label.set_text(f"❌ {message}")
    
    def _on_result_selected(self, flowbox, child):
        """Handle result selection"""
        self.select_button.set_sensitive(True)
        
        # Get the selected result
        if isinstance(child, SearchResultItem):
            self.selected_result = child.result
        else:
            self.selected_result = None
    
    def _on_select_clicked(self, button):
        """Handle select button click"""
        if not hasattr(self, 'selected_result') or not self.selected_result:
            return
        
        # Build metadata object
        result = self.selected_result
        
        # Extract year
        date = result.get('release_date') or result.get('first_air_date', '')
        year = int(date[:4]) if date and len(date) >= 4 else None
        
        # Build poster URL
        poster_path = result.get('poster_path')
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
        
        metadata = Metadata(
            title=result.get('title') or result.get('name', 'Unknown'),
            year=year,
            tmdb_id=result.get('id'),
            overview=result.get('overview'),
            poster_path=poster_path,
            poster_url=poster_url,
        )
        
        self.selected_metadata = metadata
        
        # Call callback if provided
        if self.on_select:
            self.on_select(metadata)
        
        # Close dialog
        self.close()
    
    def get_selected_metadata(self) -> Optional[Metadata]:
        """Get the selected metadata"""
        return self.selected_metadata
