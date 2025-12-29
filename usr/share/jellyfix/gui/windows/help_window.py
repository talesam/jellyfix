#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# gui/windows/help_window.py - Help and tutorial window
#

"""
Help window with comprehensive tutorials and documentation.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw

from ...utils.i18n import _
from ...utils.config import APP_VERSION


class HelpWindow(Adw.Window):
    """Help and documentation window"""

    def __init__(self, parent):
        """
        Initialize help window.

        Args:
            parent: Parent window
        """
        super().__init__(transient_for=parent, modal=True)

        # Window properties
        self.set_title(_("Jellyfix Help"))
        self.set_default_size(800, 600)

        # Build UI
        self._build_ui()

    def _build_ui(self):
        """Build help UI"""
        # Main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        # Content box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content_box.set_margin_start(40)
        content_box.set_margin_end(40)
        content_box.set_margin_top(20)
        content_box.set_margin_bottom(20)

        # Title
        title_label = Gtk.Label()
        title_label.set_markup(f'<span size="xx-large" weight="bold">🎬 Jellyfix</span>')
        title_label.set_halign(Gtk.Align.CENTER)
        content_box.append(title_label)

        # Version
        version_label = Gtk.Label()
        version_label.set_markup(f'<span size="small">{_("Version")} {APP_VERSION}</span>')
        version_label.set_halign(Gtk.Align.CENTER)
        content_box.append(version_label)

        # Description
        desc_label = Gtk.Label()
        desc_label.set_markup(f'<b>{_("Intelligent Jellyfin Library Organizer")}</b>')
        desc_label.set_halign(Gtk.Align.CENTER)
        content_box.append(desc_label)

        # Separator
        separator = Gtk.Separator()
        content_box.append(separator)

        # What It Does section
        self._add_section(content_box, _("What Jellyfix Does"), _("""
Jellyfix automatically organizes your media library following Jellyfin naming conventions:

• <b>Renames files</b> to Jellyfin standard format
• <b>Organizes episodes</b> into Season folders
• <b>Manages subtitles</b>: renames, removes foreign languages, adds language codes
• <b>Fetches metadata</b> from TMDB/TVDB
• <b>Detects and adds quality tags</b> (1080p, 720p, etc)
• <b>Adds provider IDs</b> to folder names ([tmdbid-12345])
"""))

        # Examples section
        self._add_section(content_box, _("Examples"), _("""
<b>Movies:</b>
  Before: movie.name.2023.1080p.bluray.mkv
  After:  Movie Name (2023) [tmdbid-12345]/Movie Name (2023) - 1080p.mkv

<b>TV Shows:</b>
  Before: show.name.s01e05.720p.mkv
  After:  Show Name (2024) [tmdbid-67890]/Season 01/Show Name S01E05 - 720p.mkv

<b>Subtitles:</b>
  • Renames: .por2.srt → .por.srt, .eng3.srt → .eng.srt
  • Adds language codes: subtitle.srt → Movie Name.por.srt
  • Removes foreign languages (keeps configured languages only)
  • <b>NEVER</b> removes .forced.srt files
"""))

        # How to Use section
        self._add_section(content_box, _("How to Use"), _("""
<b>1. Configure TMDB API Key (recommended)</b>
   Menu → Configure API Keys → Follow the tutorial
   This enables metadata fetching and poster downloads.

<b>2. Scan Library</b>
   Click "Scan Library" on Dashboard
   Select your media folder
   Review the scan results

<b>3. Review Operations</b>
   Switch to "Operations" tab
   Preview what will be changed
   Select operations to see details

<b>4. Execute</b>
   Click "Process Files"
   Confirm the operation
   Files will be renamed and organized

<b>Tip:</b> Always review the preview before executing!
"""))

        # Settings section
        self._add_section(content_box, _("Settings"), _("""
Configure Jellyfix behavior:

• <b>Subtitle Handling:</b> Rename variants, add language codes, remove foreign
• <b>Kept Languages:</b> Choose which subtitle languages to keep
• <b>Metadata:</b> Enable/disable TMDB fetching
• <b>Quality Tags:</b> Add resolution tags to filenames
• <b>ffprobe:</b> Use ffprobe for accurate quality detection
"""))

        # Important Notes section
        self._add_section(content_box, _("Important Notes"), _("""
⚠️ <b>Dry-run is DEFAULT</b>
Files are NOT modified unless you explicitly execute operations.

✓ <b>Always review before executing</b>
Check the operation preview carefully.

🔑 <b>Configure TMDB API</b>
For best results, configure your TMDB API key in Settings.

🌍 <b>Customize kept languages</b>
Configure which subtitle languages to keep in Preferences.
"""))

        # Links section
        links_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        links_box.set_halign(Gtk.Align.CENTER)

        links_title = Gtk.Label()
        links_title.set_markup(f'<b>{_("Links")}</b>')
        links_box.append(links_title)

        homepage_button = Gtk.LinkButton(
            uri="https://github.com/talesam/jellyfix",
            label=_("Homepage")
        )
        links_box.append(homepage_button)

        issues_button = Gtk.LinkButton(
            uri="https://github.com/talesam/jellyfix/issues",
            label=_("Report Issues")
        )
        links_box.append(issues_button)

        tmdb_button = Gtk.LinkButton(
            uri="https://www.themoviedb.org/settings/api",
            label=_("Get TMDB API Key")
        )
        links_box.append(tmdb_button)

        content_box.append(links_box)

        # Add content to scrolled window
        scrolled.set_child(content_box)
        main_box.append(scrolled)

        # Set content
        self.set_content(main_box)

    def _add_section(self, parent, title, content):
        """
        Add a help section.

        Args:
            parent: Parent widget
            title: Section title
            content: Section content (markup)
        """
        # Title
        title_label = Gtk.Label()
        title_label.set_markup(f'<span size="large" weight="bold">{title}</span>')
        title_label.set_halign(Gtk.Align.START)
        title_label.set_margin_top(10)
        parent.append(title_label)

        # Content
        content_label = Gtk.Label()
        content_label.set_markup(content.strip())
        content_label.set_wrap(True)
        content_label.set_halign(Gtk.Align.START)
        content_label.set_xalign(0)
        parent.append(content_label)
